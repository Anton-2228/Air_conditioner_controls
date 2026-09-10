from air_conditioner import AirConditioner

from .Command import Command
from .SetMode import SetMode
from .SetTemperature import SetTemperature
from .ShowMenu import ShowMenu
from .TogglePower import TogglePower

__all__ = ["Command", "SetMode", "SetTemperature", "ShowMenu", "TogglePower", "get_commands"]


def get_commands(command_manager, air_conditioner: AirConditioner) -> dict[str, Command]:
    """Реестр команд.

    TogglePower, SetMode и SetTemperature регистрируют свои callback-хендлеры
    в конструкторе, поэтому создать их нужно все, даже те, что не вызываются
    по строковому ключу.
    """
    return {
        "menu": ShowMenu(command_manager, air_conditioner),
        "togglePower": TogglePower(command_manager, air_conditioner),
        "setMode": SetMode(command_manager, air_conditioner),
        "setTemperature": SetTemperature(command_manager, air_conditioner),
    }
