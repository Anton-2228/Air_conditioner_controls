import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class BoilerError(Exception):
    """Не удалось выполнить запрос к API бойлера.

    reason:
        auth        — сервер не принял токен (401), сам не починится
        unavailable — облако розетки недоступно или розетка не в сети (502)
        network     — не достучались до сервера или он ответил не тем
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _as_float(raw: dict, key: str) -> float:
    try:
        return float(raw[key])
    except (KeyError, TypeError, ValueError):
        if key in raw:
            logger.warning("В ответе /status непонятный %s=%r, беру 0", key, raw[key])
        return 0.0


def _as_int(raw: dict, key: str) -> int:
    try:
        return int(raw[key])
    except (KeyError, TypeError, ValueError):
        if key in raw:
            logger.warning("В ответе /status непонятный %s=%r, беру 0", key, raw[key])
        return 0


@dataclass(frozen=True)
class BoilerStatus:
    """Ответ GET /status. Единственный источник истины о состоянии розетки.

    Розеткой можно управлять кнопкой на корпусе и штатным приложением,
    поэтому локальное состояние бот не хранит: после каждой команды
    состояние перечитывается с сервера.
    """

    on: bool = False
    """Реле розетки: подано ли питание."""
    watts: float = 0.0
    volts: float = 0.0
    amps: float = 0.0
    heating: bool = False
    """ТЭН реально потребляет мощность. В панели не показывается, но API
    его отдаёт, и по логам видно, греется бойлер или уже нагрел воду."""
    countdown: int = 0
    """Секунд до автовыключения по таймеру розетки. 0 — таймер не активен."""

    @classmethod
    def from_dict(cls, raw: dict) -> "BoilerStatus":
        """Собирает состояние из JSON, подставляя нули вместо непонятного.

        Сервер может обновиться раньше бота, поэтому лишние ключи
        игнорируются, а отсутствующие не должны ронять хендлер.
        """
        if not isinstance(raw, dict):
            raise BoilerError("network", f"Сервер вернул не объект: {raw!r}")
        return cls(
            on=bool(raw.get("on")),
            watts=_as_float(raw, "watts"),
            volts=_as_float(raw, "volts"),
            amps=_as_float(raw, "amps"),
            heating=bool(raw.get("heating")),
            countdown=_as_int(raw, "countdown"),
        )
