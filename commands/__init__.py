from air_conditioner import AirConditioner

from .Command import Command
from .SetMode import SetMode
from .SetPower import SetPower
from .SetTemperature import SetTemperature
from .ShowMenu import ShowMenu

__all__ = ["Command", "SetMode", "SetPower", "SetTemperature", "ShowMenu", "get_commands"]


def get_commands(command_manager, air_conditioner: AirConditioner) -> dict[str, Command]:
    """Реестр команд.

    SetPower, SetMode и SetTemperature регистрируют свои callback-хендлеры
    в конструкторе, поэтому создать их нужно все, даже те, что не вызываются
    по строковому ключу.
    """
    return {
        "menu": ShowMenu(command_manager, air_conditioner),
        "setPower": SetPower(command_manager, air_conditioner),
        "setMode": SetMode(command_manager, air_conditioner),
        "setTemperature": SetTemperature(command_manager, air_conditioner),
    }
