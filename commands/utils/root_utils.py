"""Корневое меню: выбор устройства.

Отдельный модуль, а не часть панели кондиционера или бойлера: сюда
ведёт «Назад» с обеих панелей, и зависеть от них корень не должен.
"""

import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from datafiles import ROOT_MESSAGE

logger = logging.getLogger(__name__)

CALLBACK_OPEN_AC = "root_ac"
CALLBACK_OPEN_BOILER = "root_boiler"
CALLBACK_BACK = "root_back"

BACK_BUTTON_TEXT = "⬅️ Назад"


def add_back_button(builder: InlineKeyboardBuilder) -> None:
    """Общая кнопка возврата для панелей устройств."""
    builder.button(text=BACK_BUTTON_TEXT, callback_data=CALLBACK_BACK)


def build_root_keyboard(with_boiler: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❄️ Кондиционер", callback_data=CALLBACK_OPEN_AC)
    # Без настроенного бойлера кнопки нет: вести ей некуда, а «не настроено»
    # в ответ на нажатие — худший вид ответа.
    if with_boiler:
        builder.button(text="🚿 Бойлер", callback_data=CALLBACK_OPEN_BOILER)
    builder.adjust(1)
    return builder.as_markup()


async def send_root_menu(target: Message, with_boiler: bool) -> None:
    """Новое сообщение. Нужно только для /menu и /start."""
    await target.answer(ROOT_MESSAGE, reply_markup=build_root_keyboard(with_boiler))


async def show_root_menu(callback: CallbackQuery, with_boiler: bool) -> None:
    """Возврат из панели устройства: то же сообщение, корневое содержимое.

    Новых сообщений не шлём — в чате остаётся одна панель, как и было
    до появления второго устройства.
    """
    if callback.message is None:
        return
    try:
        await callback.bot.edit_message_text(
            text=ROOT_MESSAGE,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=build_root_keyboard(with_boiler),
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            logger.warning("Не удалось вернуться в меню: %s", exc)
