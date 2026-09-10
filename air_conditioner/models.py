import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

POWER_ON = "On"
POWER_OFF = "Off"

MODE_COOL = "Cool"
MODE_HEAT = "Heat"
SUPPORTED_MODES = (MODE_COOL, MODE_HEAT)

DEFAULT_FAN_SPEED = "Auto"
DEFAULT_LIGHT = "On"


@dataclass(frozen=True)
class AcState:
    """Последняя успешно отправленная команда, а не реальное состояние кондиционера.

    Класс неизменяемый намеренно: новое состояние собирается через
    dataclasses.replace, отправляется по ИК и становится текущим только
    после подтверждения. Иначе неудачная отправка испортила бы состояние
    в памяти ещё до того, как выяснилось, что команда не дошла.
    """

    power: str = POWER_OFF
    mode: str = MODE_COOL
    temp: int = 24
    # FanSpeed и Light в меню не выводятся, но Gree сбрасывает неуказанное
    # на дефолты, поэтому хранятся и уходят в каждый payload.
    fan_speed: str = DEFAULT_FAN_SPEED
    light: str = DEFAULT_LIGHT
    updated_at: str = ""
    updated_by: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "AcState":
        """Собирает состояние из JSON, подставляя дефолты вместо всего непонятного.

        Файл состояния переживает обновления бота, поэтому лишние ключи
        игнорируются, а отсутствующие берутся из дефолтов.
        """
        defaults = cls()
        power = raw.get("power")
        if power not in (POWER_ON, POWER_OFF):
            if power is not None:
                logger.warning("В состоянии непонятный power=%r, беру %r", power, defaults.power)
            power = defaults.power

        mode = raw.get("mode")
        if mode not in SUPPORTED_MODES:
            if mode is not None:
                logger.warning("В состоянии непонятный mode=%r, беру %r", mode, defaults.mode)
            mode = defaults.mode

        try:
            temp = int(raw["temp"])
        except (KeyError, TypeError, ValueError):
            if "temp" in raw:
                logger.warning(
                    "В состоянии непонятный temp=%r, беру %s", raw["temp"], defaults.temp
                )
            temp = defaults.temp

        updated_by = raw.get("updated_by")
        if not isinstance(updated_by, int):
            updated_by = None

        return cls(
            power=power,
            mode=mode,
            temp=temp,
            fan_speed=str(raw.get("fan_speed") or defaults.fan_speed),
            light=str(raw.get("light") or defaults.light),
            updated_at=str(raw.get("updated_at") or ""),
            updated_by=updated_by,
        )


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
