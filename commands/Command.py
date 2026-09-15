from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from air_conditioner import AirConditioner


class Command:
    """Базовый класс команды."""

    def __init__(self, command_manager, air_conditioner: AirConditioner | None = None) -> None:
        # air_conditioner необязателен: команды бойлера ходят к своему
        # устройству и про кондиционер ничего не знают.
        self.commandManager = command_manager
        self.air_conditioner: AirConditioner = air_conditioner

    async def execute(
        self,
        message: Message,
        state: FSMContext,
        command: CommandObject | None = None,
    ) -> None:
        pass
