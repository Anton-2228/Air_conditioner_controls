import logging

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from .Command import Command
from .utils.keyboards import CALLBACK_POWER_TOGGLE
from .utils.menu_utils import ack_callback, report_result

logger = logging.getLogger(__name__)


class TogglePower(Command):
    """Кнопка-тумблер питания. ИК уходит всегда, в том числе на выключение."""

    def __init__(self, command_manager, air_conditioner) -> None:
        super().__init__(command_manager, air_conditioner)
        command_manager.router.callback_query.register(
            self.toggle_power, F.data == CALLBACK_POWER_TOGGLE
        )

    async def toggle_power(self, callback: CallbackQuery, state: FSMContext) -> None:
        ack_callback(callback)
        if callback.message is None:
            return
        # Читаем актуальное состояние внутри сервиса под локом, а не подпись
        # кнопки: сообщение могло быть отправлено давно и уже устареть.
        result = await self.air_conditioner.toggle_power(callback.message.chat.id)
        await report_result(callback, result, self.air_conditioner)
