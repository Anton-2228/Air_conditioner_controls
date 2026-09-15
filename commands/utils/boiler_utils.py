import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from boiler import STATE_HEATING, STATE_OFF, STATE_READY, Boiler, BoilerError, BoilerStatus
from datafiles import BOILER_AUTH_MESSAGE, BOILER_MESSAGE, BOILER_UNAVAILABLE_MESSAGE

logger = logging.getLogger(__name__)

CALLBACK_BOILER_ON = "boiler_on"
CALLBACK_BOILER_OFF = "boiler_off"

STATE_TITLES = {
    STATE_OFF: "🔴 Выключен",
    STATE_HEATING: "🔥 Греется",
    # Питание подано, но термостат снял нагрузку — это не ошибка,
    # а самое полезное состояние: вода уже горячая.
    STATE_READY: "✅ Вода готова",
}

UNKNOWN_STATE = "⏳ нет данных"
NO_VALUE = "—"


def _mark(active: bool, text: str) -> str:
    return ("✅ " if active else "") + text


def build_boiler_keyboard(status: BoilerStatus | None) -> InlineKeyboardMarkup:
    """Две кнопки: подать питание и снять.

    Не тумблер: розеткой управляют ещё кнопкой на корпусе и штатным
    приложением, поэтому нажатие должно слать конкретное состояние,
    а не переключать то, что бот считает текущим.
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
    builder.adjust(2)
    return builder.as_markup()


def format_countdown(seconds: int) -> str:
    """Секунды в «1 ч 20 мин». 0 — таймер не активен."""
    if seconds <= 0:
        return "нет"
    minutes = max(1, round(seconds / 60))
    hours, minutes = divmod(minutes, 60)
    if hours and minutes:
        left = f"{hours} ч {minutes} мин"
    elif hours:
        left = f"{hours} ч"
    else:
        left = f"{minutes} мин"
    return f"выключится через {left}"


def format_boiler_status(status: BoilerStatus | None, note: str | None = None) -> str:
    """Текст панели. status=None — состояние узнать не удалось.

    Note — разовая приписка о результате последнего действия; отдельным
    сообщением её не шлём, чтобы в чате оставалась одна панель.
    """
    if status is None:
        text = BOILER_MESSAGE.format(state=UNKNOWN_STATE, power=NO_VALUE, timer=NO_VALUE)
    else:
        text = BOILER_MESSAGE.format(
            state=STATE_TITLES.get(status.state, status.state),
            # Ватты интересны, только когда идёт нагрев: в остальное время
            # это ноль, который ничего не говорит.
            power=f"{status.watts:.0f} Вт" if status.heating else NO_VALUE,
            timer=format_countdown(status.countdown),
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


async def send_boiler_menu(target: Message, boiler: Boiler) -> None:
    """Новая панель. Нужна только для /boiler — редактировать там нечего."""
    status, note = await fetch_status(boiler)
    await target.answer(
        format_boiler_status(status, note),
        reply_markup=build_boiler_keyboard(status),
    )


async def update_boiler_menu(
    callback: CallbackQuery,
    status: BoilerStatus | None,
    note: str | None = None,
) -> None:
    """Перерисовывает ту самую панель, на кнопку которой нажали."""
    if callback.message is None:
        return
    try:
        await callback.bot.edit_message_text(
            text=format_boiler_status(status, note),
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=build_boiler_keyboard(status),
        )
    except TelegramBadRequest as exc:
        # «message is not modified» — нормальная ситуация: нажали кнопку,
        # которая ничего не изменила. Остальное стоит увидеть в логах.
        if "message is not modified" not in str(exc):
            logger.warning("Не удалось обновить панель бойлера: %s", exc)
