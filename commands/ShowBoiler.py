from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from boiler import Boiler

from .Command import Command
from .utils.boiler_utils import send_boiler_menu


class ShowBoiler(Command):
    """/boiler — панель бойлера: состояние и две кнопки."""

    def __init__(self, command_manager, boiler: Boiler) -> None:
        super().__init__(command_manager)
        self.boiler = boiler

    async def execute(
        self,
        message: Message,
        state: FSMContext,
        command: CommandObject | None = None,
    ) -> None:
        await send_boiler_menu(message, self.boiler)
