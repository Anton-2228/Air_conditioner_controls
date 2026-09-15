from air_conditioner import AirConditioner
from boiler import Boiler

from .Command import Command
from .Navigate import Navigate
from .RefreshBoiler import RefreshBoiler
from .SetBoilerPower import SetBoilerPower
from .SetMode import SetMode
from .SetPower import SetPower
from .SetTemperature import SetTemperature
from .ShowMenu import ShowMenu

__all__ = [
    "Command",
    "Navigate",
    "RefreshBoiler",
    "SetBoilerPower",
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
        "navigate": Navigate(command_manager, air_conditioner, boiler),
        "setPower": SetPower(command_manager, air_conditioner),
        "setMode": SetMode(command_manager, air_conditioner),
        "setTemperature": SetTemperature(command_manager, air_conditioner),
    }
    if boiler is not None:
        commands["setBoilerPower"] = SetBoilerPower(command_manager, boiler)
        commands["refreshBoiler"] = RefreshBoiler(command_manager, boiler)
    return commands
