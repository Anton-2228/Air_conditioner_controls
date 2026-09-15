import logging

from aiogram import F
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from boiler import Boiler, BoilerError, DelayedStart
from datafiles import (
    BOILER_TIMER_BAD_INPUT_MESSAGE,
    BOILER_TIMER_DELAY_MESSAGE,
    BOILER_TIMER_DURATION_MESSAGE,
)

from .Command import Command
from .utils.boiler_utils import (
    CALLBACK_TIMER_BACK,
    CALLBACK_TIMER_CANCEL,
    CALLBACK_TIMER_NOW,
    CALLBACK_TIMER_OPEN,
    build_boiler_keyboard,
    build_timer_delay_keyboard,
    build_timer_duration_keyboard,
    fetch_status,
    format_boiler_status,
    format_duration,
    note_for_error,
    parse_hh_mm,
    show_boiler_panel,
)
from .utils.menu_utils import ack_callback

logger = logging.getLogger(__name__)


class TimerDialog(StatesGroup):
    """Два шага: через сколько включить и на сколько."""

    delay = State()
    duration = State()


class SetBoilerTimer(Command):
    """Кнопка «Задать таймер» и диалог за ней.

    Пауза до включения отсчитывается ботом, а длительность нагрева уходит
    в саму розетку: до выключения дело доведёт она, даже если бот умрёт.
    """

    def __init__(self, command_manager, boiler: Boiler, delayed_start: DelayedStart) -> None:
        super().__init__(command_manager)
        self.boiler = boiler
        self.delayed_start = delayed_start
        router = command_manager.router
        router.callback_query.register(self.open, F.data == CALLBACK_TIMER_OPEN)
        router.callback_query.register(self.skip_delay, F.data == CALLBACK_TIMER_NOW)
        router.callback_query.register(self.back_to_delay, F.data == CALLBACK_TIMER_BACK)
        router.callback_query.register(self.cancel, F.data == CALLBACK_TIMER_CANCEL)
        # Команды пропускаем мимо: /menu должен работать и посреди диалога,
        # иначе из него не выбраться ничем, кроме кнопок.
        text_input = F.text & ~F.text.startswith("/")
        router.message.register(self.on_delay, StateFilter(TimerDialog.delay), text_input)
        router.message.register(self.on_duration, StateFilter(TimerDialog.duration), text_input)

    async def open(self, callback: CallbackQuery, state: FSMContext) -> None:
        ack_callback(callback)
        if callback.message is None:
            return
        # Запоминаем панель: дальше пользователь отвечает сообщениями,
        # а перерисовывать нужно её же, а не плодить новые.
        await state.set_state(TimerDialog.delay)
        await state.update_data(
            panel_chat_id=callback.message.chat.id,
            panel_message_id=callback.message.message_id,
        )
        await self._edit(
            callback.bot,
            callback.message.chat.id,
            callback.message.message_id,
            BOILER_TIMER_DELAY_MESSAGE,
            build_timer_delay_keyboard(),
        )

    async def skip_delay(self, callback: CallbackQuery, state: FSMContext) -> None:
        """«Включить сразу» — это нулевая пауза, а не отдельный сценарий."""
        ack_callback(callback)
        if callback.message is None:
            return
        await self._go_to_duration(
            callback.bot, callback.message.chat.id, callback.message.message_id, state, 0
        )

    async def back_to_delay(self, callback: CallbackQuery, state: FSMContext) -> None:
        ack_callback(callback)
        if callback.message is None:
            return
        await state.set_state(TimerDialog.delay)
        await self._edit(
            callback.bot,
            callback.message.chat.id,
            callback.message.message_id,
            BOILER_TIMER_DELAY_MESSAGE,
            build_timer_delay_keyboard(),
        )

    async def cancel(self, callback: CallbackQuery, state: FSMContext) -> None:
        """Выход из диалога. Уже идущий таймер не трогаем: его отменяют
        кнопками «Включить» и «Выключить», а не отказом от настройки нового."""
        ack_callback(callback)
        await state.clear()
        await show_boiler_panel(callback, self.boiler, self.delayed_start)

    async def on_delay(self, message: Message, state: FSMContext) -> None:
        minutes = parse_hh_mm(message.text or "")
        data = await state.get_data()
        await self._drop_user_message(message)
        if minutes is None:
            await self._edit(
                message.bot,
                data["panel_chat_id"],
                data["panel_message_id"],
                f"{BOILER_TIMER_DELAY_MESSAGE}\n\n{BOILER_TIMER_BAD_INPUT_MESSAGE}",
                build_timer_delay_keyboard(),
            )
            return
        await self._go_to_duration(
            message.bot, data["panel_chat_id"], data["panel_message_id"], state, minutes
        )

    async def on_duration(self, message: Message, state: FSMContext) -> None:
        minutes = parse_hh_mm(message.text or "")
        data = await state.get_data()
        delay = data.get("delay_minutes", 0)
        await self._drop_user_message(message)
        # Нулевая длительность — это «включить и не выключать», а такое
        # делается кнопкой «Включить». Здесь это почти наверняка опечатка.
        if not minutes:
            await self._edit(
                message.bot,
                data["panel_chat_id"],
                data["panel_message_id"],
                self._duration_text(delay) + f"\n\n{BOILER_TIMER_BAD_INPUT_MESSAGE}",
                build_timer_duration_keyboard(),
            )
            return

        await state.clear()
        note = await self._apply(delay, minutes)
        status, error_note = await fetch_status(self.boiler)
        await self._edit(
            message.bot,
            data["panel_chat_id"],
            data["panel_message_id"],
            format_boiler_status(status, error_note or note, self.delayed_start.plan),
            build_boiler_keyboard(status),
        )

    async def _apply(self, delay: int, duration: int) -> str:
        """Ставит таймер и возвращает приписку для панели."""
        if delay == 0:
            try:
                await self.boiler.turn_on(duration)
            except BoilerError as exc:
                logger.warning("Не удалось включить бойлер по таймеру: %s", exc)
                return note_for_error(exc)
            return f"⏱ Включил на {format_duration(duration)}"
        plan = self.delayed_start.schedule(delay, duration)
        return (
            f"⏱ Включится через {format_duration(delay)} "
            f"на {format_duration(plan.duration_minutes)}"
        )

    async def _go_to_duration(self, bot, chat_id: int, message_id: int, state, delay: int) -> None:
        await state.set_state(TimerDialog.duration)
        await state.update_data(delay_minutes=delay)
        await self._edit(
            bot, chat_id, message_id, self._duration_text(delay), build_timer_duration_keyboard()
        )

    @staticmethod
    def _duration_text(delay: int) -> str:
        start = "Включаю сразу." if delay == 0 else f"Включу через {format_duration(delay)}."
        return BOILER_TIMER_DURATION_MESSAGE.format(start=start)

    @staticmethod
    async def _drop_user_message(message: Message) -> None:
        """Убирает «01:30» из чата, чтобы диалог оставался одним сообщением.

        В личке бот вправе удалять входящие, но право можно и потерять —
        неудача здесь не повод ронять обработку.
        """
        try:
            await message.delete()
        except TelegramAPIError as exc:
            logger.debug("Не удалось убрать сообщение пользователя: %s", exc)

    @staticmethod
    async def _edit(bot, chat_id: int, message_id: int, text: str, markup) -> None:
        try:
            await bot.edit_message_text(
                text=text, chat_id=chat_id, message_id=message_id, reply_markup=markup
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc):
                logger.warning("Не удалось обновить диалог таймера: %s", exc)
