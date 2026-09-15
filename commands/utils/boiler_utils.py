import logging
import re

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from boiler import Boiler, BoilerError, BoilerStatus, DelayedStart, Plan
from datafiles import BOILER_AUTH_MESSAGE, BOILER_MESSAGE, BOILER_UNAVAILABLE_MESSAGE

from .root_utils import add_back_button

logger = logging.getLogger(__name__)

CALLBACK_BOILER_ON = "boiler_on"
CALLBACK_BOILER_OFF = "boiler_off"
CALLBACK_BOILER_REFRESH = "boiler_refresh"
CALLBACK_TIMER_OPEN = "boiler_timer"
CALLBACK_TIMER_NOW = "boiler_timer_now"
CALLBACK_TIMER_BACK = "boiler_timer_back"
CALLBACK_TIMER_CANCEL = "boiler_timer_cancel"

UNKNOWN_STATE = "⏳ нет данных"

# Розетка отсчитывает не больше суток, дольше держать смысла нет и боту.
MAX_MINUTES = 24 * 60

_TIME_PATTERN = re.compile(r"^(\d{1,2}):([0-5]\d)$")


def _mark(active: bool, text: str) -> str:
    return ("✅ " if active else "") + text


def build_boiler_keyboard(status: BoilerStatus | None) -> InlineKeyboardMarkup:
    """Панель бойлера.

    Включение и выключение — не тумблер: розеткой управляют ещё кнопкой
    на корпусе и штатным приложением, поэтому нажатие шлёт конкретное
    состояние, а не переключает то, что бот считает текущим.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_mark(status is not None and status.on, "🟢 Включить"),
        callback_data=CALLBACK_BOILER_ON,
    )
    builder.button(
        text=_mark(status is not None and not status.on, "🔴 Выключить"),
        callback_data=CALLBACK_BOILER_OFF,
    )
    builder.button(text="⏱ Задать таймер", callback_data=CALLBACK_TIMER_OPEN)
    # Панель не обновляется сама, а бойлер живёт своей жизнью: отсчитывается
    # таймер, кто-то щёлкает кнопкой на розетке. «Обновить» — способ это увидеть.
    builder.button(text="🔄 Обновить", callback_data=CALLBACK_BOILER_REFRESH)
    add_back_button(builder)
    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()


def build_timer_delay_keyboard() -> InlineKeyboardMarkup:
    """Шаг 1: через сколько включить."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡ Включить сразу", callback_data=CALLBACK_TIMER_NOW)
    builder.button(text="❌ Отменить", callback_data=CALLBACK_TIMER_CANCEL)
    builder.adjust(1, 1)
    return builder.as_markup()


def build_timer_duration_keyboard() -> InlineKeyboardMarkup:
    """Шаг 2: сколько держать включённым."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data=CALLBACK_TIMER_BACK)
    builder.button(text="❌ Отменить", callback_data=CALLBACK_TIMER_CANCEL)
    builder.adjust(1, 1)
    return builder.as_markup()


def parse_hh_mm(text: str) -> int | None:
    """«01:30» → 90 минут. None — не разобрали или вышли за сутки.

    Минуты строго двузначные: «1:5» — это опечатка, а не пять минут,
    и угадывать здесь опаснее, чем переспросить.
    """
    match = _TIME_PATTERN.match(text.strip())
    if match is None:
        return None
    minutes = int(match.group(1)) * 60 + int(match.group(2))
    return minutes if minutes <= MAX_MINUTES else None


def format_duration(minutes: int) -> str:
    """90 → «1 ч 30 мин». Ноль сюда не приходит."""
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours} ч {rest} мин"
    if hours:
        return f"{hours} ч"
    return f"{rest} мин"


def format_countdown(seconds: int, plan: Plan | None = None) -> str:
    """Строка таймера в панели.

    Отложенное включение показываем вместо отсчёта розетки: пока бойлер
    выключен, отсчитывать ей нечего, а ждать пользователю есть чего.
    """
    if plan is not None:
        start = format_duration(max(1, round(plan.seconds_left / 60)))
        return f"включится через {start} на {format_duration(plan.duration_minutes)}"
    if seconds <= 0:
        return "нет"
    return f"выключится через {format_duration(max(1, round(seconds / 60)))}"


def format_boiler_status(
    status: BoilerStatus | None,
    note: str | None = None,
    plan: Plan | None = None,
) -> str:
    """Текст панели. status=None — состояние узнать не удалось.

    Note — разовая приписка о результате последнего действия; отдельным
    сообщением её не шлём, чтобы в чате оставалась одна панель.
    """
    if status is None:
        text = BOILER_MESSAGE.format(state=UNKNOWN_STATE, timer=format_countdown(0, plan))
    else:
        text = BOILER_MESSAGE.format(
            state="🟢 Включен" if status.on else "🔴 Выключен",
            timer=format_countdown(status.countdown, plan),
        )
    if note:
        text += f"\n\n{note}"
    return text


def note_for_error(exc: BoilerError) -> str:
    # Неверный токен — поломка настройки, её чинит владелец бота.
    # Всё остальное — временная потеря связи, её чинит повтор.
    return BOILER_AUTH_MESSAGE if exc.reason == "auth" else BOILER_UNAVAILABLE_MESSAGE


async def fetch_status(boiler: Boiler) -> tuple[BoilerStatus | None, str | None]:
    """Состояние и приписка об ошибке. Ошибка связи не должна ронять хендлер."""
    try:
        return await boiler.get_status(), None
    except BoilerError as exc:
        logger.warning("Не удалось получить состояние бойлера: %s", exc)
        return None, note_for_error(exc)


async def update_boiler_menu(
    callback: CallbackQuery,
    status: BoilerStatus | None,
    note: str | None = None,
    plan: Plan | None = None,
) -> None:
    """Перерисовывает ту самую панель, на кнопку которой нажали."""
    if callback.message is None:
        return
    try:
        await callback.bot.edit_message_text(
            text=format_boiler_status(status, note, plan),
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=build_boiler_keyboard(status),
        )
    except TelegramBadRequest as exc:
        # «message is not modified» — нормальная ситуация: нажали кнопку,
        # которая ничего не изменила. Остальное стоит увидеть в логах.
        if "message is not modified" not in str(exc):
            logger.warning("Не удалось обновить панель бойлера: %s", exc)


async def show_boiler_panel(
    callback: CallbackQuery,
    boiler: Boiler,
    delayed_start: DelayedStart,
    note: str | None = None,
) -> None:
    """Перечитать состояние и показать панель — общий путь для всех кнопок,
    которые возвращают пользователя к бойлеру."""
    status, error_note = await fetch_status(boiler)
    await update_boiler_menu(callback, status, note or error_note, delayed_start.plan)
