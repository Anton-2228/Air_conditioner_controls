import logging

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from .Command import Command
from .utils.keyboards import CALLBACK_POWER_OFF, CALLBACK_POWER_ON, POWER_BY_CALLBACK
from .utils.menu_utils import ack_callback, report_result

logger = logging.getLogger(__name__)


class SetPower(Command):
    """Отдельные кнопки включения и выключения. ИК уходит при каждом нажатии."""

    def __init__(self, command_manager, air_conditioner) -> None:
        super().__init__(command_manager, air_conditioner)
        command_manager.router.callback_query.register(
            self.set_power, F.data.in_({CALLBACK_POWER_ON, CALLBACK_POWER_OFF})
        )

    async def set_power(self, callback: CallbackQuery, state: FSMContext) -> None:
        ack_callback(callback)
        if callback.message is None:
            return
        power = POWER_BY_CALLBACK.get(callback.data)
        if power is None:
            logger.warning("Непонятный callback_data питания: %r", callback.data)
            return
        result = await self.air_conditioner.set_power(power, callback.message.chat.id)
        await report_result(callback, result, self.air_conditioner)
