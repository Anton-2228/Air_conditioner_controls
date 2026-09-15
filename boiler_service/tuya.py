"""Розетка глазами tuya-device-sharing-sdk.

Здесь заканчивается вся специфика Tuya: наружу отдаются ватты, вольты
и амперы, а не десятые доли и миллиамперы. Если розетку когда-нибудь
перепрошьют на Tasmota, переписать нужно будет только этот файл.
"""

import json
import logging
import os
import threading
import time

from tuya_sharing import Manager, SharingTokenListener

logger = logging.getLogger(__name__)

# Регистрация приложения Home Assistant в экосистеме Tuya. Аккаунт
# разработчика с его пробным периодом не нужен: вход сделан по QR-коду
# из мобильного приложения, поэтому доступ не протухнет через месяц.
CLIENT_ID = "HA_3y9q4ak7g4ephrvke"

# Датапоинты розетки
DP_SWITCH = "switch_1"
DP_COUNTDOWN = "countdown_1"
DP_POWER = "cur_power"  # десятые доли ватта
DP_VOLTAGE = "cur_voltage"  # десятые доли вольта
DP_CURRENT = "cur_current"  # миллиамперы

# Ниже этого порога считаем, что ТЭН не работает: сама розетка потребляет
# меньше ватта, а бойлер в нагреве — около полутора киловатт.
HEATING_WATTS = 100.0


class TuyaError(RuntimeError):
    """Облако недоступно, розетка не в сети или токен больше не годится."""


class _TokenFile(SharingTokenListener):
    """SDK сам обновляет токен по refresh_token.

    Обновлённый нужно записать на диск, иначе после перезапуска сервиса
    придётся заново сканировать QR-код.
    """

    def __init__(self, path: str) -> None:
        self.path = path

    def read(self) -> dict:
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def update_token(self, token_info: dict) -> None:
        data = self.read()
        data["token_info"] = token_info
        # Пишем через временный файл: обрыв посреди записи оставил бы
        # обрезанный JSON, а это тот самый QR-код заново.
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)
        logger.info("Токен Tuya обновлён и сохранён")


class Socket:
    """Умная розетка: включить, выключить, прочитать показания.

    SDK синхронный и не потокобезопасный, а FastAPI зовёт обработчики
    из пула потоков, поэтому всё общение с облаком идёт под локом.
    """

    def __init__(self, device_id: str, token_file: str, cache_ttl: float = 3.0) -> None:
        self._device_id = device_id
        self._tokens = _TokenFile(token_file)
        self._cache_ttl = cache_ttl
        self._lock = threading.Lock()
        self._manager: Manager | None = None
        self._cached: dict | None = None
        self._cached_at = 0.0

    def status(self) -> dict:
        """Показания розетки. Свежесть — не хуже cache_ttl секунд.

        Кэш нужен, чтобы не упираться в лимиты облака: панель бойлера
        открыта у нескольких человек, а состояние меняется медленно.
        """
        with self._lock:
            if self._cached is not None and time.time() - self._cached_at < self._cache_ttl:
                return self._cached
            raw = self._read_device()
            self._cached = self._to_reading(raw)
            self._cached_at = time.time()
            return self._cached

    def turn_on(self, minutes: int = 0) -> None:
        """Подаёт питание. minutes > 0 — ещё и заводит таймер.

        Таймер отсчитывает сама розетка, поэтому он сработает, даже если
        этот сервис упадёт или пропадёт интернет. Порядок важен: сначала
        питание, потом таймер, иначе включение сбросило бы отсчёт.
        """
        commands = [(DP_SWITCH, True)]
        if minutes > 0:
            commands.append((DP_COUNTDOWN, minutes * 60))
        self._send(commands)

    def turn_off(self) -> None:
        """Снимает питание и сбрасывает таймер.

        Таймер сбрасываем первым: иначе он остался бы висеть и через час
        неожиданно включил бы бойлер обратно.
        """
        self._send([(DP_COUNTDOWN, 0), (DP_SWITCH, False)])

    def _send(self, commands: list[tuple[str, object]]) -> None:
        payload = [{"code": code, "value": value} for code, value in commands]
        with self._lock:
            manager = self._get_manager()
            try:
                manager.send_commands(self._device_id, payload)
            except Exception as exc:
                raise TuyaError(str(exc)) from exc
            # Состояние заведомо поменялось — держать старое нельзя.
            self._cached = None
            self._cached_at = 0.0
        logger.info("Отправлено розетке: %s", payload)

    def _get_manager(self) -> Manager:
        # Ленивое подключение: если при старте контейнера облако лежит,
        # сервис должен подняться и отвечать 502, а не падать в рестарт-цикл.
        if self._manager is None:
            cfg = self._tokens.read()
            try:
                manager = Manager(
                    CLIENT_ID,
                    cfg["user_code"],
                    cfg["terminal_id"],
                    cfg["endpoint"],
                    cfg["token_info"],
                    self._tokens,
                )
                manager.update_device_cache()
            except Exception as exc:
                raise TuyaError(str(exc)) from exc
            if self._device_id not in manager.device_map:
                raise TuyaError(f"устройство {self._device_id} не найдено в аккаунте")
            self._manager = manager
            logger.info("Подключился к Tuya, устройство %s на месте", self._device_id)
        return self._manager

    def _read_device(self) -> dict:
        manager = self._get_manager()
        try:
            manager.update_device_cache()
            return manager.device_map[self._device_id].status
        except Exception as exc:
            # Manager мог протухнуть вместе с сессией — пересоберём в следующий раз.
            self._manager = None
            raise TuyaError(str(exc)) from exc

    @staticmethod
    def _to_reading(raw: dict) -> dict:
        """Датапоинты — в привычные единицы.

        Реле и ТЭН — разные вещи: термостат бойлера снимает нагрузку,
        когда вода нагрелась, а питание при этом остаётся поданным.
        """
        watts = raw.get(DP_POWER, 0) / 10
        return {
            "on": bool(raw.get(DP_SWITCH)),
            "watts": watts,
            "volts": raw.get(DP_VOLTAGE, 0) / 10,
            "amps": raw.get(DP_CURRENT, 0) / 1000,
            "heating": watts > HEATING_WATTS,
            "countdown": int(raw.get(DP_COUNTDOWN, 0)),
        }
