from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from boiler import Boiler

from .Command import Command
from .utils.root_utils import send_root_menu


class ShowMenu(Command):
    """/start и /menu — корневое меню: выбор устройства."""

    def __init__(self, command_manager, air_conditioner, boiler: Boiler | None = None) -> None:
        super().__init__(command_manager, air_conditioner)
        self.with_boiler = boiler is not None

    async def execute(
        self,
        message: Message,
        state: FSMContext,
        command: CommandObject | None = None,
    ) -> None:
        await send_root_menu(message, self.with_boiler)
