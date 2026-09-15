import logging

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from boiler import Boiler, BoilerError
from datafiles import BOILER_PENDING_MESSAGE

from .Command import Command
from .utils.boiler_utils import (
    CALLBACK_BOILER_OFF,
    CALLBACK_BOILER_ON,
    note_for_error,
    update_boiler_menu,
)
from .utils.menu_utils import ack_callback

logger = logging.getLogger(__name__)


class SetBoilerPower(Command):
    """Кнопки «Включить» и «Выключить» под панелью бойлера."""

    def __init__(self, command_manager, boiler: Boiler) -> None:
        super().__init__(command_manager)
        self.boiler = boiler
        command_manager.router.callback_query.register(
            self.set_power, F.data.in_({CALLBACK_BOILER_ON, CALLBACK_BOILER_OFF})
        )

    async def set_power(self, callback: CallbackQuery, state: FSMContext) -> None:
        ack_callback(callback)
        if callback.message is None:
            return
        turn_on = callback.data == CALLBACK_BOILER_ON
        try:
            if turn_on:
                # Без таймера: пока это осознанный выбор из двух кнопок.
                await self.boiler.turn_on()
            else:
                await self.boiler.turn_off()
        except BoilerError as exc:
            logger.warning("Команда бойлеру не прошла (%s): %s", exc.reason, exc)
            await update_boiler_menu(callback, None, note_for_error(exc))
            return

        # Команда принята, но реле переключится через облако не сразу.
        # Показываем это честно, а через пару секунд перечитываем состояние:
        # источник истины — всегда /status, а не то, что мы отправили.
        await update_boiler_menu(callback, None, BOILER_PENDING_MESSAGE)
        try:
            status = await self.boiler.status_after_command()
        except BoilerError as exc:
            logger.warning("Не удалось перечитать состояние бойлера: %s", exc)
            await update_boiler_menu(callback, None, note_for_error(exc))
            return
        await update_boiler_menu(callback, status)
