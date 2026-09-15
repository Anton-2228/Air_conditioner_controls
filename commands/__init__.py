from air_conditioner import AirConditioner
from boiler import Boiler

from .Command import Command
from .SetBoilerPower import SetBoilerPower
from .SetMode import SetMode
from .SetPower import SetPower
from .SetTemperature import SetTemperature
from .ShowBoiler import ShowBoiler
from .ShowMenu import ShowMenu

__all__ = [
    "Command",
    "SetBoilerPower",
    "SetMode",
    "SetPower",
    "SetTemperature",
    "ShowBoiler",
    "ShowMenu",
    "get_commands",
]


def get_commands(
    command_manager,
    air_conditioner: AirConditioner,
    boiler: Boiler | None = None,
) -> dict[str, Command]:
    """Реестр команд.

    SetPower, SetMode, SetTemperature и SetBoilerPower регистрируют свои
    callback-хендлеры в конструкторе, поэтому создать их нужно все, даже
    те, что не вызываются по строковому ключу.

    boiler=None — бойлер не настроен: его команды не создаются, и кнопок,
    которые всё равно некуда отправить, в чате не появляется.
    """
    commands: dict[str, Command] = {
        "menu": ShowMenu(command_manager, air_conditioner),
        "setPower": SetPower(command_manager, air_conditioner),
        "setMode": SetMode(command_manager, air_conditioner),
        "setTemperature": SetTemperature(command_manager, air_conditioner),
    }
    if boiler is not None:
        commands["boiler"] = ShowBoiler(command_manager, boiler)
        commands["setBoilerPower"] = SetBoilerPower(command_manager, boiler)
    return commands
