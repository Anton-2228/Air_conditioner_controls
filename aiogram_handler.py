import asyncio
import logging

from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, Message

from command_manager import CommandManager
from commands import get_commands
from datafiles import INTERNAL_ERROR_MESSAGE, UNCLEAR_INPUT_MESSAGE
from init import COMMANDS, air_conditioner, bot, dp, mqtt_wrapper, router

logger = logging.getLogger(__name__)

commandManager = CommandManager(router=router, bot=bot)
commandManager.addCommands(get_commands(commandManager, air_conditioner))


@router.message(Command("start"))
@router.message(Command("menu"))
async def menu(
    message: Message,
    state: FSMContext,
    command: CommandObject | None = None,
) -> None:
    await commandManager.launchCommand("menu", message, state, command)


# Catch-all регистрируется последним: он перехватывает всё, что не разобрали выше.
@router.message()
async def unclear_input(
    message: Message,
    state: FSMContext,
    command: CommandObject | None = None,
) -> None:
    await message.answer(UNCLEAR_INPUT_MESSAGE)


@dp.errors()
async def on_error(event: ErrorEvent) -> bool:
    logger.exception("Необработанная ошибка при обработке апдейта", exc_info=event.exception)
    # Пытаемся ответить пользователю, но молча переживаем и неудачу этой попытки:
    # исключение отсюда попало бы обратно в диспетчер.
    target = event.update.message
    if target is None and event.update.callback_query is not None:
        target = event.update.callback_query.message
    if target is not None:
        try:
            await target.answer(INTERNAL_ERROR_MESSAGE)
        except TelegramAPIError:
            logger.warning("Не удалось сообщить пользователю об ошибке")
    return True


async def start_polling() -> None:
    # Меню команд — удобство, а не необходимость. Если Telegram сейчас
    # недоступен, бот не должен из-за этого падать: polling сам умеет
    # переживать сетевые ошибки и переподключаться.
    try:
        await bot.set_my_commands(commands=COMMANDS)
    except TelegramAPIError as exc:
        logger.warning("Не удалось выставить меню команд: %s", exc)
    dp.include_routers(router)
    logger.info("Запускаю long polling")
    await dp.start_polling(bot)


async def start() -> None:
    await asyncio.gather(start_polling(), mqtt_wrapper.run())


if __name__ == "__main__":
    asyncio.run(start())
