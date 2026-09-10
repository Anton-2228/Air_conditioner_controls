import json
from dataclasses import FrozenInstanceError

import pytest

from air_conditioner import BASE_PAYLOAD_KEYS, AcProtocol, AcState, build_hvac_payload, dump_payload

GREE = AcProtocol(vendor="Gree", model="YAW1F", min_temp=17, max_temp=30, send_light=True)

# Эталон из desc.txt
REFERENCE_ON = {
    "Vendor": "Gree",
    "Model": "YAW1F",
    "Power": "On",
    "Mode": "Cool",
    "Temp": 24,
    "FanSpeed": "Auto",
    "Light": "On",
}


def test_payload_matches_reference_from_desc():
    state = AcState(power="On", mode="Cool", temp=24)
    assert build_hvac_payload(state, GREE) == REFERENCE_ON


def test_payload_keeps_all_fields_when_power_off():
    """Главный инвариант Gree: короткий payload сбросил бы режим и подсветку."""
    payload = build_hvac_payload(AcState(power="Off", mode="Heat", temp=28), GREE)
    assert set(payload) == BASE_PAYLOAD_KEYS | {"Model", "Light"}
    assert payload["Power"] == "Off"
    assert payload["Mode"] == "Heat"
    assert payload["Light"] == "On"


@pytest.mark.parametrize("power", ["On", "Off"])
@pytest.mark.parametrize("mode", ["Cool", "Heat"])
@pytest.mark.parametrize("temp", range(17, 31))
def test_payload_never_misses_a_field(power, mode, temp):
    payload = build_hvac_payload(AcState(power=power, mode=mode, temp=temp), GREE)
    assert set(payload) >= BASE_PAYLOAD_KEYS


def test_temp_survives_json_as_number():
    restored = json.loads(dump_payload(build_hvac_payload(AcState(temp=24), GREE)))
    assert restored["Temp"] == 24
    assert isinstance(restored["Temp"], int)


def test_vendor_and_model_come_from_protocol():
    other = AcProtocol(vendor="Haier", model="", send_light=False)
    payload = build_hvac_payload(AcState(), other)
    assert payload["Vendor"] == "Haier"
    assert "Model" not in payload  # пустая модель — ключ не отправляем
    assert "Light" not in payload  # протокол подсветку не понимает


def test_model_omitted_only_when_empty():
    payload = build_hvac_payload(AcState(), AcProtocol(vendor="Electra", model="ЧТО-ТО"))
    assert payload["Model"] == "ЧТО-ТО"


def test_base_keys_always_present_for_any_protocol():
    """Vendor/Power/Mode/Temp/FanSpeed нужны любому вендору."""
    for protocol in [GREE, AcProtocol(vendor="Haier", model="", send_light=False)]:
        assert set(build_hvac_payload(AcState(), protocol)) >= BASE_PAYLOAD_KEYS


def test_fan_speed_and_light_defaults():
    state = AcState()
    assert state.fan_speed == "Auto"
    assert state.light == "On"


def test_dump_payload_is_compact():
    assert " " not in dump_payload(build_hvac_payload(AcState(), GREE))


def test_state_is_immutable():
    with pytest.raises(FrozenInstanceError):
        AcState().temp = 25
