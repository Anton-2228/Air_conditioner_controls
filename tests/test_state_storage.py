import asyncio
import json

import pytest

from air_conditioner import AcProtocol, AcState, AirConditioner, StateStorage


class FakeMqtt:
    """Подменяет MqttWrapper: сеть в тестах не поднимаем."""

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.sent: list[dict] = []
        self.last_error: str | None = None
        self.board_online: bool | None = True

    async def send_hvac(self, payload: dict) -> bool:
        if not self.ok:
            self.last_error = "offline"
            return False
        self.sent.append(payload)
        await asyncio.sleep(0)  # даём шанс переключению задач, чтобы гонка была настоящей
        return True


@pytest.fixture
def storage(tmp_path):
    return StateStorage(tmp_path / "state.json")


def test_round_trip(storage):
    state = AcState(power="On", mode="Heat", temp=28, updated_by=42)
    storage.save(state)
    assert storage.load() == state


def test_missing_file_gives_defaults(storage):
    assert storage.load() == AcState()
    assert not storage.path.exists()


def test_broken_json_gives_defaults(storage):
    storage.path.write_text("{не json", encoding="utf-8")
    assert storage.load() == AcState()


def test_json_array_gives_defaults(storage):
    storage.path.write_text("[1, 2, 3]", encoding="utf-8")
    assert storage.load() == AcState()


def test_missing_keys_fall_back_to_defaults(storage):
    storage.path.write_text('{"power": "On"}', encoding="utf-8")
    state = storage.load()
    assert state.power == "On"
    assert state.mode == AcState().mode
    assert state.temp == AcState().temp
    assert state.fan_speed == "Auto"


def test_unknown_keys_are_ignored(storage):
    storage.path.write_text('{"power": "On", "swing": "Vertical"}', encoding="utf-8")
    assert storage.load().power == "On"


def test_temp_as_string_is_coerced(storage):
    storage.path.write_text('{"temp": "24"}', encoding="utf-8")
    assert storage.load().temp == 24


def test_garbage_temp_falls_back(storage):
    storage.path.write_text('{"temp": "жарко"}', encoding="utf-8")
    assert storage.load().temp == AcState().temp


def test_unsupported_mode_falls_back(storage):
    """Dry/Fan/Auto в меню нет — если такое попало в файл, берём дефолт."""
    storage.path.write_text('{"mode": "Dry"}', encoding="utf-8")
    assert storage.load().mode == AcState().mode


def test_no_temp_files_left_behind(storage):
    storage.save(AcState())
    assert [p.name for p in storage.path.parent.iterdir()] == [storage.path.name]


async def test_concurrent_updates_are_serialized(storage):
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    await ac.set_power("On", 1)  # включаем, чтобы ИК действительно уходил

    temps = list(range(17, 31))
    await asyncio.gather(*[ac.set_temperature(t, 1) for t in temps])

    assert ac.get_state().temp in temps
    on_disk = json.loads(storage.path.read_text(encoding="utf-8"))
    assert on_disk["temp"] == ac.get_state().temp
    # включение + по одной публикации на каждую температуру
    assert len(mqtt.sent) == len(temps) + 1


async def test_failed_send_leaves_state_untouched(storage):
    ok_mqtt = FakeMqtt()
    ac = AirConditioner(storage, ok_mqtt)
    await ac.set_power("On", 1)
    before = ac.get_state()
    before_on_disk = storage.path.read_text(encoding="utf-8")

    ac._mqtt = FakeMqtt(ok=False)
    result = await ac.set_temperature(29, 1)

    assert result.ok is False
    assert result.error == "offline"
    assert ac.get_state() == before
    assert storage.path.read_text(encoding="utf-8") == before_on_disk


async def test_change_while_off_is_saved_but_not_sent(storage):
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    assert ac.get_state().power == "Off"

    result = await ac.set_mode("Heat", 1)

    assert result.ok is True
    assert result.ir_sent is False
    assert mqtt.sent == []
    assert json.loads(storage.path.read_text(encoding="utf-8"))["mode"] == "Heat"


async def test_saved_mode_is_applied_on_power_on(storage):
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    await ac.set_mode("Heat", 1)
    await ac.set_temperature(19, 1)

    result = await ac.set_power("On", 1)

    assert result.ok is True
    assert mqtt.sent[-1]["Power"] == "On"
    assert mqtt.sent[-1]["Mode"] == "Heat"
    assert mqtt.sent[-1]["Temp"] == 19


async def test_power_off_still_sends_ir(storage):
    """Выключение обязано уйти по ИК, даже хотя итоговый power=Off."""
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    await ac.set_power("On", 1)
    mqtt.sent.clear()

    result = await ac.set_power("Off", 1)

    assert result.ir_sent is True
    assert mqtt.sent[-1]["Power"] == "Off"


async def test_power_off_when_already_off_still_sends(storage):
    """Кнопки идемпотентны: «Выключить» шлёт выключение, даже если бот считает
    кондиционер выключенным. Так чинится рассинхрон с пультом с первого нажатия."""
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    assert ac.get_state().power == "Off"

    result = await ac.set_power("Off", 1)

    assert result.ir_sent is True
    assert mqtt.sent[-1]["Power"] == "Off"


async def test_power_on_when_already_on_still_sends(storage):
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    await ac.set_power("On", 1)
    mqtt.sent.clear()

    await ac.set_power("On", 1)

    assert len(mqtt.sent) == 1
    assert mqtt.sent[-1]["Power"] == "On"


async def test_set_power_rejects_garbage(storage):
    ac = AirConditioner(storage, FakeMqtt())
    with pytest.raises(ValueError):
        await ac.set_power("Maybe", 1)


async def test_step_temperature_moves_by_one(storage):
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    await ac.set_power("On", 1)
    start = ac.get_state().temp

    up = await ac.step_temperature(1, 1)
    assert up.ok is True
    assert up.unchanged is False
    assert ac.get_state().temp == start + 1

    await ac.step_temperature(-1, 1)
    assert ac.get_state().temp == start


async def test_step_temperature_stops_at_upper_limit(storage):
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    await ac.set_power("On", 1)
    await ac.set_temperature(30, 1)
    mqtt.sent.clear()

    result = await ac.step_temperature(1, 1)

    assert result.unchanged is True
    assert result.ok is True
    assert ac.get_state().temp == 30
    assert mqtt.sent == []  # на границе ИК не шлём


async def test_step_temperature_stops_at_lower_limit(storage):
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    await ac.set_power("On", 1)
    await ac.set_temperature(17, 1)
    mqtt.sent.clear()

    result = await ac.step_temperature(-1, 1)

    assert result.unchanged is True
    assert ac.get_state().temp == 17
    assert mqtt.sent == []


async def test_step_temperature_while_off_is_saved_only(storage):
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    assert ac.get_state().power == "Off"

    result = await ac.step_temperature(1, 1)

    assert result.ok is True
    assert result.ir_sent is False
    assert mqtt.sent == []
    assert json.loads(storage.path.read_text(encoding="utf-8"))["temp"] == 25


async def test_stepping_across_whole_range(storage):
    """От 24 можно дойти до обеих границ и упереться."""
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    await ac.set_power("On", 1)

    for _ in range(20):
        await ac.step_temperature(1, 1)
    assert ac.get_state().temp == 30

    for _ in range(20):
        await ac.step_temperature(-1, 1)
    assert ac.get_state().temp == 17


async def test_custom_range_from_protocol(storage):
    """Диапазон задаётся протоколом: у другого кондиционера он свой."""
    mqtt = FakeMqtt()
    protocol = AcProtocol(vendor="Haier", model="", min_temp=16, max_temp=26)
    ac = AirConditioner(storage, mqtt, protocol)
    await ac.set_power("On", 1)

    for _ in range(20):
        await ac.step_temperature(-1, 1)
    assert ac.get_state().temp == 16

    for _ in range(20):
        await ac.step_temperature(1, 1)
    assert ac.get_state().temp == 26


async def test_protocol_shapes_the_payload(storage):
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt, AcProtocol(vendor="Haier", model="", send_light=False))
    await ac.set_power("On", 1)

    assert mqtt.sent[-1]["Vendor"] == "Haier"
    assert "Model" not in mqtt.sent[-1]
    assert "Light" not in mqtt.sent[-1]


async def test_state_survives_restart(storage):
    mqtt = FakeMqtt()
    ac = AirConditioner(storage, mqtt)
    await ac.set_power("On", 1)
    await ac.set_temperature(21, 1)

    restarted = AirConditioner(StateStorage(storage.path), FakeMqtt())
    assert restarted.get_state().power == "On"
    assert restarted.get_state().temp == 21
