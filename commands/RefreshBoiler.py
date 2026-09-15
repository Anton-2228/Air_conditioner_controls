import logging

from aiogram import F
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from boiler import Boiler, DelayedStart

from .Command import Command
from .utils.boiler_utils import CALLBACK_BOILER_REFRESH, fetch_status, update_boiler_menu

logger = logging.getLogger(__name__)


class RefreshBoiler(Command):
    """Кнопка «Обновить»: перечитать состояние розетки."""

    def __init__(self, command_manager, boiler: Boiler, delayed_start: DelayedStart) -> None:
        super().__init__(command_manager)
        self.boiler = boiler
        self.delayed_start = delayed_start
        command_manager.router.callback_query.register(
            self.refresh, F.data == CALLBACK_BOILER_REFRESH
        )

    async def refresh(self, callback: CallbackQuery, state: FSMContext) -> None:
        logger.info("Нажата кнопка %s", callback.data)
        note = None
        if callback.message is not None:
            status, note = await fetch_status(self.boiler)
            await update_boiler_menu(callback, status, note, self.delayed_start.plan)
        # «Часики» гасим после запроса, а не до: пока бот ходит к розетке,
        # они честно показывают, что нажатие обрабатывается. Всплывающая
        # подсказка нужна, потому что состояние чаще всего не меняется —
        # без неё кнопка выглядела бы мёртвой.
        try:
            await callback.answer("Состояние обновлено" if note is None else None)
        except TelegramAPIError as exc:
            logger.warning("Не удалось погасить «часики» на кнопке: %s", exc)
