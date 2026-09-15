from air_conditioner import AirConditioner
from boiler import Boiler, DelayedStart

from .Command import Command
from .Navigate import Navigate
from .RefreshBoiler import RefreshBoiler
from .SetBoilerPower import SetBoilerPower
from .SetBoilerTimer import SetBoilerTimer
from .SetMode import SetMode
from .SetPower import SetPower
from .SetTemperature import SetTemperature
from .ShowMenu import ShowMenu

__all__ = [
    "Command",
    "Navigate",
    "RefreshBoiler",
    "SetBoilerPower",
    "SetBoilerTimer",
    "SetMode",
    "SetPower",
    "SetTemperature",
    "ShowMenu",
    "get_commands",
]


def get_commands(
    command_manager,
    air_conditioner: AirConditioner,
    boiler: Boiler | None = None,
    delayed_start: DelayedStart | None = None,
) -> dict[str, Command]:
    """Реестр команд.

    Все, кроме ShowMenu, регистрируют свои callback-хендлеры в конструкторе,
    поэтому создать их нужно все, даже те, что не вызываются по строковому
    ключу: в бота ведёт одна команда /menu, дальше — только кнопки.

    boiler=None — бойлер не настроен: его кнопки и хендлеры не создаются,
    в корневом меню остаётся один кондиционер.
    """
    commands: dict[str, Command] = {
        "menu": ShowMenu(command_manager, air_conditioner, boiler),
        "navigate": Navigate(command_manager, air_conditioner, boiler, delayed_start),
        "setPower": SetPower(command_manager, air_conditioner),
        "setMode": SetMode(command_manager, air_conditioner),
        "setTemperature": SetTemperature(command_manager, air_conditioner),
    }
    if boiler is not None:
        if delayed_start is None:
            raise ValueError("С бойлером нужен и DelayedStart: без него таймер не поставить")
        commands["setBoilerPower"] = SetBoilerPower(command_manager, boiler, delayed_start)
        commands["setBoilerTimer"] = SetBoilerTimer(command_manager, boiler, delayed_start)
        commands["refreshBoiler"] = RefreshBoiler(command_manager, boiler, delayed_start)
    return commands
