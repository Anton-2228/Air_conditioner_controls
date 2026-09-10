import json

from .models import AcState
from .protocol import AcProtocol

BASE_PAYLOAD_KEYS = frozenset({"Vendor", "Power", "Mode", "Temp", "FanSpeed"})


def build_hvac_payload(state: AcState, protocol: AcProtocol) -> dict:
    """Собирает аргумент команды IRhvac.

    Все поля отправляются всегда, включая выключение: протоколы вроде Gree
    передают состояние целиком, поэтому укороченный payload сбросил бы режим
    и погасил дисплей.

    Model и Light необязательны — не у всех вендоров они есть, а лишний ключ
    Tasmota отвергает целиком.
    """
    payload = {
        "Vendor": protocol.vendor,
        "Power": state.power,
        "Mode": state.mode,
        "Temp": state.temp,
        "FanSpeed": state.fan_speed,
    }
    if protocol.model:
        payload["Model"] = protocol.model
    if protocol.send_light:
        payload["Light"] = state.light
    return payload


def dump_payload(payload: dict) -> str:
    """Компактный JSON — у Tasmota ограничен буфер MQTT-сообщения."""
    return json.dumps(payload, separators=(",", ":"))
