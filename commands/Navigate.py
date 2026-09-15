import logging

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from air_conditioner import AirConditioner
from boiler import Boiler, DelayedStart

from .Command import Command
from .utils.boiler_utils import show_boiler_panel
from .utils.menu_utils import ack_callback, update_menu
from .utils.root_utils import CALLBACK_BACK, CALLBACK_OPEN_AC, CALLBACK_OPEN_BOILER, show_root_menu

logger = logging.getLogger(__name__)


class Navigate(Command):
    """Переходы между корневым меню и панелями устройств.

    Всё происходит в одном сообщении: выбор устройства разворачивает его
    панель на месте, «Назад» сворачивает обратно. Новых сообщений в чате
    не появляется — как и раньше, панель в диалоге одна.
    """

    def __init__(
        self,
        command_manager,
        air_conditioner: AirConditioner,
        boiler: Boiler | None = None,
        delayed_start: DelayedStart | None = None,
    ) -> None:
        super().__init__(command_manager, air_conditioner)
        self.boiler = boiler
        self.delayed_start = delayed_start
        router = command_manager.router
        router.callback_query.register(self.open_air_conditioner, F.data == CALLBACK_OPEN_AC)
        router.callback_query.register(self.back, F.data == CALLBACK_BACK)
        if boiler is not None:
            router.callback_query.register(self.open_boiler, F.data == CALLBACK_OPEN_BOILER)

    async def open_air_conditioner(self, callback: CallbackQuery, state: FSMContext) -> None:
        ack_callback(callback)
        await update_menu(callback, self.air_conditioner)

    async def open_boiler(self, callback: CallbackQuery, state: FSMContext) -> None:
        ack_callback(callback)
        if callback.message is None:
            return
        # Состояние розетки читается при каждом открытии: локального
        # состояния у бойлера нет, показывать нечего, кроме свежего ответа.
        await show_boiler_panel(callback, self.boiler, self.delayed_start)

    async def back(self, callback: CallbackQuery, state: FSMContext) -> None:
        ack_callback(callback)
        # Возврат в корень закрывает и недонастроенный таймер: оставлять
        # диалог висеть в состоянии, из которого ушли, незачем.
        await state.clear()
        await show_root_menu(callback, self.boiler is not None)
