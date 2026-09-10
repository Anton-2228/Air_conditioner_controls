import logging

from aiogram import Bot, Router
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

logger = logging.getLogger(__name__)


class CommandManager:
    def __init__(self, router: Router, bot: Bot) -> None:
        self.commands = {}
        self.router = router
        self.bot = bot

    def addCommands(self, commands: dict) -> None:
        self.commands.update(commands)

    def getCommands(self) -> dict:
        return self.commands

    async def launchCommand(
        self,
        title: str,
        message: Message,
        state: FSMContext,
        command: CommandObject | None = None,
    ) -> None:
        await self.commands[title].execute(message, state, command)
