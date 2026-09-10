from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .Command import Command
from .utils.menu_utils import send_menu


class ShowMenu(Command):
    """/start и /menu — одно и то же меню."""

    async def execute(
        self,
        message: Message,
        state: FSMContext,
        command: CommandObject | None = None,
    ) -> None:
        await send_menu(message, self.air_conditioner)
