import asyncio
import json
import logging

import aiomqtt

from air_conditioner import dump_payload

logger = logging.getLogger(__name__)

ONLINE = "Online"

# Ключ, по которому в ответе Tasmota опознаётся именно наша команда.
# Без этой проверки любой другой RESULT (например ответ на Status) дал бы
# ложное подтверждение отправки.
#
# Одного ключа мало: отказ приходит под тем же ключом. Успех —
# {"IRHVAC":{"Vendor":...}}, отказ — {"IRHVAC":"Wrong Vendor (...)"}.
# Различаются они только типом значения.
ACK_KEY = "IRHVAC"


class MqttWrapper:
    """Одно долгоживущее соединение с брокером.

    Публикация ИК-команды устроена по схеме «одна команда в полёте»:
    корреляции по id в Tasmota нет, ответ всегда приходит в один и тот же
    топик stat/<топик>/RESULT, поэтому одновременно ждать двух подтверждений
    нельзя. Выше по стеку AirConditioner держит собственный лок, так что
    команды и так приходят по одной.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        base_topic: str,
        client_id: str,
        ack_timeout: float = 5.0,
        repeat_delay: float = 0.3,
        reconnect_delay: float = 5.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._client_id = client_id
        self._ack_timeout = ack_timeout
        self._repeat_delay = repeat_delay
        self._reconnect_delay = reconnect_delay

        self.cmnd_topic = f"cmnd/{base_topic}/IRhvac"
        self.stat_topic = f"stat/{base_topic}/RESULT"
        self.lwt_topic = f"tele/{base_topic}/LWT"

        self._client: aiomqtt.Client | None = None
        self._connected = asyncio.Event()
        self._publish_lock = asyncio.Lock()
        self._ack_waiter: asyncio.Future | None = None

        self.board_online: bool | None = None
        """None — LWT ещё не приходил, состояние платы неизвестно."""
        self.last_error: str | None = None
        self._rejected: str | None = None
        """Текст отказа Tasmota на последнюю команду, если она её отвергла."""

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    async def run(self) -> None:
        """Бесконечный цикл соединения. Не завершается никогда.

        aiomqtt сам не переподключается, поэтому переподключение наше.
        Задача крутится рядом с polling в asyncio.gather, и её падение
        уронило бы бота — отсюда перехват всех исключений.
        """
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=self._host,
                    port=self._port,
                    username=self._username or None,
                    password=self._password or None,
                    identifier=self._client_id,
                    keepalive=30,
                ) as client:
                    self._client = client
                    self._connected.set()
                    logger.info("MQTT подключён к %s:%s", self._host, self._port)
                    await client.subscribe(self.lwt_topic, qos=1)
                    await client.subscribe(self.stat_topic, qos=1)
                    async for message in client.messages:
                        self._handle_message(message)
            except aiomqtt.MqttError as exc:
                logger.warning(
                    "MQTT-соединение потеряно: %s. Переподключение через %s c",
                    exc,
                    self._reconnect_delay,
                )
            except Exception:
                logger.exception("Непредвиденная ошибка MQTT-цикла")
            finally:
                self._client = None
                self._connected.clear()
                # Разбудить ждущего подтверждения, иначе он зря провисит до таймаута.
                self._fail_pending_ack()
            await asyncio.sleep(self._reconnect_delay)

    def _fail_pending_ack(self) -> None:
        waiter = self._ack_waiter
        if waiter is not None and not waiter.done():
            waiter.set_result(False)

    def _handle_message(self, message) -> None:
        topic = str(message.topic)
        payload = message.payload.decode("utf-8", errors="replace")

        if topic == self.lwt_topic:
            was = self.board_online
            self.board_online = payload.strip() == ONLINE
            if was != self.board_online:
                logger.info(
                    "Плата %s (LWT=%s)",
                    "на связи" if self.board_online else "offline",
                    payload,
                )
            return

        if topic != self.stat_topic:
            return

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.debug("В %s пришёл не JSON: %r", topic, payload)
            return

        if not isinstance(data, dict) or ACK_KEY not in data:
            logger.debug("В %s пришёл посторонний ответ: %r", topic, payload)
            return

        waiter = self._ack_waiter
        answer = data[ACK_KEY]
        if not isinstance(answer, dict):
            # Плата разобрала JSON, но команду отвергла — ИК не уходил.
            # Будим ждущего сразу, чтобы не ждать таймаута впустую.
            logger.error("Плата отвергла команду: %s", answer)
            self._rejected = str(answer)
            if waiter is not None and not waiter.done():
                waiter.set_result(False)
            return

        logger.debug("Подтверждение отправки: %r", payload)
        if waiter is not None and not waiter.done():
            waiter.set_result(True)

    async def send_hvac(self, payload: dict) -> bool:
        """Публикует команду дважды и возвращает, подтвердилась ли первая посылка.

        Дубль безопасен: Gree передаёт полное состояние, а не «переключи».
        """
        async with self._publish_lock:
            if not self._connected.is_set():
                self.last_error = "not_connected"
                logger.warning("Нет соединения с брокером, команда не отправлена")
                return False
            if self.board_online is False:
                self.last_error = "offline"
                logger.warning("Плата отмечена как offline, команда не отправлена")
                return False

            body = dump_payload(payload)
            self._rejected = None

            if not await self._publish_once(body):
                self.last_error = "rejected" if self._rejected else "no_ack"
                return False

            await asyncio.sleep(self._repeat_delay)
            if not await self._publish_once(body):
                # Сигнал ушёл, потерялось только подтверждение дубля.
                # Переспрашивать не будем, чтобы не сыпать ИК-кадрами.
                logger.warning("Повторная посылка не подтверждена, команда считается успешной")

            self.last_error = None
            return True

    async def _publish_once(self, body: str) -> bool:
        client = self._client
        if client is None:
            return False
        loop = asyncio.get_running_loop()
        self._ack_waiter = loop.create_future()
        try:
            await client.publish(self.cmnd_topic, body, qos=1)
            logger.info("Опубликовано в %s: %s", self.cmnd_topic, body)
            return await asyncio.wait_for(self._ack_waiter, timeout=self._ack_timeout)
        except TimeoutError:
            logger.warning("Нет ответа в %s за %s c", self.stat_topic, self._ack_timeout)
            return False
        except aiomqtt.MqttError as exc:
            logger.warning("Публикация не удалась: %s", exc)
            return False
        finally:
            # Поздние подтверждения после этого отбрасываются.
            self._ack_waiter = None
