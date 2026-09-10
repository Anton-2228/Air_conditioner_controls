import asyncio
import json

import aiomqtt
import pytest

from mqtt_wrapper import MqttWrapper
from mqtt_wrapper import mqtt_wrapper as mqtt_module

PAYLOAD = {
    "Vendor": "Gree",
    "Model": "YAW1F",
    "Power": "On",
    "Mode": "Cool",
    "Temp": 24,
    "FanSpeed": "Auto",
    "Light": "On",
}


class FakeMessage:
    def __init__(self, topic: str, payload: str) -> None:
        self.topic = topic
        self.payload = payload.encode("utf-8")


class FakeClient:
    """Подменяет aiomqtt.Client. Ведёт себя как Tasmota: на публикацию
    в cmnd отвечает в stat, если auto_ack включён."""

    instances: list["FakeClient"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.subscribed: list[str] = []
        self.published: list[tuple[str, str]] = []
        self.queue: asyncio.Queue = asyncio.Queue()
        self.auto_ack = True
        self.ack_body = '{"IRHVAC":{"Vendor":"Gree","Power":"On"}}'
        self.fail_on_publish = False
        FakeClient.instances.append(self)

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def subscribe(self, topic: str, qos: int = 0) -> None:
        self.subscribed.append(topic)

    async def publish(self, topic: str, body: str, qos: int = 0) -> None:
        if self.fail_on_publish:
            raise aiomqtt.MqttError("публикация не удалась")
        self.published.append((topic, body))
        if self.auto_ack:
            await self.queue.put(FakeMessage("stat/tasmota_TEST/RESULT", self.ack_body))

    async def emit(self, topic: str, payload: str) -> None:
        await self.queue.put(FakeMessage(topic, payload))

    @property
    def messages(self):
        return self._iterate()

    async def _iterate(self):
        while True:
            item = await self.queue.get()
            if isinstance(item, Exception):
                raise item  # так же, как aiomqtt при разрыве соединения
            yield item


@pytest.fixture
def fake_client(monkeypatch):
    FakeClient.instances.clear()
    monkeypatch.setattr(mqtt_module.aiomqtt, "Client", FakeClient)
    return FakeClient


def make_wrapper() -> MqttWrapper:
    return MqttWrapper(
        host="localhost",
        port=1883,
        username="bot",
        password="x",
        base_topic="tasmota_TEST",
        client_id="ac_bot_test",
        ack_timeout=0.3,
        repeat_delay=0.01,
        reconnect_delay=0.01,
    )


async def start(wrapper: MqttWrapper) -> asyncio.Task:
    task = asyncio.create_task(wrapper.run())
    for _ in range(200):
        if wrapper.is_connected:
            return task
        await asyncio.sleep(0.005)
    task.cancel()
    raise AssertionError("подключение не состоялось")


async def stop(task: asyncio.Task) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_topics_are_derived_from_base():
    wrapper = make_wrapper()
    assert wrapper.cmnd_topic == "cmnd/tasmota_TEST/IRhvac"
    assert wrapper.stat_topic == "stat/tasmota_TEST/RESULT"
    assert wrapper.lwt_topic == "tele/tasmota_TEST/LWT"


async def test_subscribes_to_lwt_and_stat(fake_client):
    wrapper = make_wrapper()
    task = await start(wrapper)
    await asyncio.sleep(0.02)
    assert set(fake_client.instances[0].subscribed) == {wrapper.lwt_topic, wrapper.stat_topic}
    await stop(task)


async def test_publishes_twice_and_confirms(fake_client):
    """Каждая команда уходит дважды: ИК-канал односторонний, дубль безопасен."""
    wrapper = make_wrapper()
    task = await start(wrapper)
    client = fake_client.instances[0]
    await client.emit(wrapper.lwt_topic, "Online")
    await asyncio.sleep(0.02)

    assert await wrapper.send_hvac(PAYLOAD) is True
    assert len(client.published) == 2
    topic, body = client.published[0]
    assert topic == wrapper.cmnd_topic
    assert json.loads(body) == PAYLOAD
    assert " " not in body  # компактный JSON, буфер Tasmota невелик
    assert client.published[0] == client.published[1]
    assert wrapper.last_error is None
    await stop(task)


async def test_no_ack_gives_failure(fake_client):
    wrapper = make_wrapper()
    task = await start(wrapper)
    client = fake_client.instances[0]
    client.auto_ack = False
    await client.emit(wrapper.lwt_topic, "Online")
    await asyncio.sleep(0.02)

    assert await wrapper.send_hvac(PAYLOAD) is False
    assert wrapper.last_error == "no_ack"
    assert len(client.published) == 1  # вторую посылку не делаем, первая не подтвердилась
    await stop(task)


async def test_foreign_result_is_not_an_ack(fake_client):
    """Ответ на другую команду не должен считаться подтверждением ИК-отправки."""
    wrapper = make_wrapper()
    task = await start(wrapper)
    client = fake_client.instances[0]
    client.ack_body = '{"Command":"Unknown"}'
    await client.emit(wrapper.lwt_topic, "Online")
    await asyncio.sleep(0.02)

    assert await wrapper.send_hvac(PAYLOAD) is False
    assert wrapper.last_error == "no_ack"
    await stop(task)


async def test_wrong_vendor_is_a_rejection_not_an_ack(fake_client):
    """На неверный вендор Tasmota отвечает тем же ключом IRHVAC, но строкой.

    Раньше это засчитывалось как подтверждение: бот рапортовал об успехе
    и сохранял состояние, хотя ИК не уходил вовсе.
    """
    wrapper = make_wrapper()
    task = await start(wrapper)
    client = fake_client.instances[0]
    client.ack_body = '{"IRHVAC":"Wrong Vendor (LG|COOLIX|GREE|ELECTRA_AC)"}'
    await client.emit(wrapper.lwt_topic, "Online")
    await asyncio.sleep(0.02)

    loop = asyncio.get_running_loop()
    started = loop.time()
    assert await wrapper.send_hvac(PAYLOAD) is False
    assert wrapper.last_error == "rejected"
    assert len(client.published) == 1  # после отказа дубль не шлём
    # Отказ приходит сразу — ждать таймаут подтверждения незачем
    assert loop.time() - started < 0.2
    await stop(task)


async def test_rejection_does_not_leak_into_next_command(fake_client):
    wrapper = make_wrapper()
    task = await start(wrapper)
    client = fake_client.instances[0]
    await client.emit(wrapper.lwt_topic, "Online")
    await asyncio.sleep(0.02)

    client.ack_body = '{"IRHVAC":"Wrong Vendor"}'
    assert await wrapper.send_hvac(PAYLOAD) is False

    client.ack_body = '{"IRHVAC":{"Vendor":"ELECTRA_AC","Power":"On"}}'
    assert await wrapper.send_hvac(PAYLOAD) is True
    assert wrapper.last_error is None
    await stop(task)


async def test_broken_json_in_stat_does_not_crash(fake_client):
    wrapper = make_wrapper()
    task = await start(wrapper)
    client = fake_client.instances[0]
    client.auto_ack = False
    await client.emit(wrapper.stat_topic, "не json")
    await asyncio.sleep(0.02)

    assert wrapper.is_connected  # цикл жив
    await stop(task)


async def test_offline_board_short_circuits(fake_client):
    wrapper = make_wrapper()
    task = await start(wrapper)
    client = fake_client.instances[0]
    await client.emit(wrapper.lwt_topic, "Offline")
    await asyncio.sleep(0.02)

    assert wrapper.board_online is False
    assert await wrapper.send_hvac(PAYLOAD) is False
    assert wrapper.last_error == "offline"
    assert client.published == []  # даже не пытались публиковать
    await stop(task)


async def test_lwt_switches_back_to_online(fake_client):
    wrapper = make_wrapper()
    task = await start(wrapper)
    client = fake_client.instances[0]
    await client.emit(wrapper.lwt_topic, "Offline")
    await asyncio.sleep(0.02)
    await client.emit(wrapper.lwt_topic, "Online")
    await asyncio.sleep(0.02)

    assert wrapper.board_online is True
    assert await wrapper.send_hvac(PAYLOAD) is True
    await stop(task)


async def test_unknown_board_state_still_sends(fake_client):
    """Пока LWT не приходил, board_online = None — команду всё равно пробуем."""
    wrapper = make_wrapper()
    task = await start(wrapper)
    assert wrapper.board_online is None
    assert await wrapper.send_hvac(PAYLOAD) is True
    await stop(task)


async def test_not_connected_gives_failure(fake_client):
    wrapper = make_wrapper()  # run() не запускали
    assert await wrapper.send_hvac(PAYLOAD) is False
    assert wrapper.last_error == "not_connected"


async def test_publish_error_gives_failure(fake_client):
    wrapper = make_wrapper()
    task = await start(wrapper)
    client = fake_client.instances[0]
    client.fail_on_publish = True

    assert await wrapper.send_hvac(PAYLOAD) is False
    assert wrapper.last_error == "no_ack"
    await stop(task)


async def test_run_survives_broken_connection_and_reconnects(fake_client):
    """Задача крутится в asyncio.gather рядом с polling — упасть она не имеет права."""
    wrapper = make_wrapper()
    task = await start(wrapper)
    first = fake_client.instances[0]

    # Роняем соединение так же, как это сделал бы разрыв сети
    await first.queue.put(aiomqtt.MqttError("соединение разорвано"))
    await asyncio.sleep(0.05)

    assert not task.done()
    for _ in range(200):
        if len(fake_client.instances) > 1 and wrapper.is_connected:
            break
        await asyncio.sleep(0.005)
    assert len(fake_client.instances) > 1
    assert wrapper.is_connected
    await stop(task)
