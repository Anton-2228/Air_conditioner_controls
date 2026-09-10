import logging

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from .Command import Command
from .utils.keyboards import CALLBACK_MODE_COOL, CALLBACK_MODE_HEAT, MODE_BY_CALLBACK
from .utils.menu_utils import ack_callback, report_result

logger = logging.getLogger(__name__)


class SetMode(Command):
    """Выбор режима: охлаждение или нагрев."""

    def __init__(self, command_manager, air_conditioner) -> None:
        super().__init__(command_manager, air_conditioner)
        command_manager.router.callback_query.register(
            self.set_mode, F.data.in_({CALLBACK_MODE_COOL, CALLBACK_MODE_HEAT})
        )

    async def set_mode(self, callback: CallbackQuery, state: FSMContext) -> None:
        ack_callback(callback)
        if callback.message is None:
            return
        mode = MODE_BY_CALLBACK.get(callback.data)
        if mode is None:
            logger.warning("Непонятный callback_data режима: %r", callback.data)
            return
        result = await self.air_conditioner.set_mode(mode, callback.message.chat.id)
        await report_result(callback, result, self.air_conditioner)
