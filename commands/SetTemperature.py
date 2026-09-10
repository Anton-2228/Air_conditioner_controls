import logging

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from .Command import Command
from .utils.keyboards import (
    CALLBACK_NOOP,
    CALLBACK_TEMP_DOWN,
    CALLBACK_TEMP_UP,
    TEMP_DELTA_BY_CALLBACK,
)
from .utils.menu_utils import ack_callback, report_result

logger = logging.getLogger(__name__)


class SetTemperature(Command):
    """Температура стрелками, по градусу за нажатие."""

    def __init__(self, command_manager, air_conditioner) -> None:
        super().__init__(command_manager, air_conditioner)
        command_manager.router.callback_query.register(
            self.step_temperature, F.data.in_({CALLBACK_TEMP_UP, CALLBACK_TEMP_DOWN})
        )
        command_manager.router.callback_query.register(self.noop, F.data == CALLBACK_NOOP)

    async def step_temperature(self, callback: CallbackQuery, state: FSMContext) -> None:
        ack_callback(callback)
        if callback.message is None:
            return
        delta = TEMP_DELTA_BY_CALLBACK.get(callback.data)
        if delta is None:
            logger.warning("Непонятный callback_data температуры: %r", callback.data)
            return
        result = await self.air_conditioner.step_temperature(delta, callback.message.chat.id)
        await report_result(callback, result, self.air_conditioner)

    async def noop(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Средняя кнопка с текущим значением: гасим «часики» и всё."""
        await callback.answer()
