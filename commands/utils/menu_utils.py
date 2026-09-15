import asyncio
import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from air_conditioner import MODE_COOL, MODE_HEAT, POWER_ON, AcState, AirConditioner, CommandResult
from datafiles import (
    BOARD_OFFLINE_MESSAGE,
    COMMAND_REJECTED_MESSAGE,
    LIMIT_REACHED_MESSAGE,
    MENU_MESSAGE,
    SAVED_ONLY_MESSAGE,
)

from .keyboards import build_menu_keyboard

logger = logging.getLogger(__name__)

MODE_TITLES = {
    MODE_COOL: "❄️ Охлаждение",
    MODE_HEAT: "🔥 Нагрев",
}

# Ссылки на задачи держим сами: asyncio их не хранит, и без этого
# сборщик мусора может убить задачу до завершения.
_pending_acks: set[asyncio.Task] = set()


def _on_ack_done(task: asyncio.Task) -> None:
    _pending_acks.discard(task)
    exc = task.exception()
    if exc is not None:
        logger.warning("Не удалось погасить «часики» на кнопке: %s", exc)


async def _answer(callback: CallbackQuery) -> None:
    # callback.answer() возвращает объект метода API, а не корутину:
    # он awaitable, но asyncio.create_task такое не принимает, поэтому
    # нужна настоящая корутина-обёртка.
    await callback.answer()


def ack_callback(callback: CallbackQuery) -> None:
    """Гасит «часики» на кнопке, не задерживая отправку команды.

    callback.answer() — это запрос к api.telegram.org, целый сетевой
    round-trip. Дожидаться его перед публикацией в MQTT означало бы
    добавить его к задержке до первой ИК-посылки, поэтому шлём параллельно.
    """
    logger.info("Нажата кнопка %s", callback.data)
    task = asyncio.create_task(_answer(callback))
    _pending_acks.add(task)
    task.add_done_callback(_on_ack_done)


def format_status(state: AcState, board_online: bool | None, note: str | None = None) -> str:
    """Текст панели.

    Показывается целиком всегда, в том числе при выключенном кондиционере:
    видно, с какими настройками он запустится. Note — разовая приписка
    о результате последнего действия; отдельным сообщением её не шлём,
    чтобы в чате оставалась одна панель.
    """
    if board_online is None:
        board = "⏳ нет данных"
    elif board_online:
        board = "🟢 на связи"
    else:
        board = "🔴 недоступна"

    text = MENU_MESSAGE.format(
        power="🟢 Включён" if state.power == POWER_ON else "🔴 Выключен",
        mode=MODE_TITLES.get(state.mode, state.mode),
        temp=state.temp,
        board=board,
    )
    if note:
        text += f"\n\n{note}"
    return text


async def update_menu(
    callback: CallbackQuery,
    air_conditioner: AirConditioner,
    note: str | None = None,
) -> None:
    """Перерисовывает ту самую панель, на кнопку которой нажали."""
    if callback.message is None:
        return
    state = air_conditioner.get_state()
    try:
        await callback.bot.edit_message_text(
            text=format_status(state, air_conditioner.board_online, note),
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=build_menu_keyboard(state),
        )
    except TelegramBadRequest as exc:
        # «message is not modified» — нормальная ситуация: нажали кнопку,
        # которая ничего не изменила. Остальное стоит увидеть в логах.
        if "message is not modified" not in str(exc):
            logger.warning("Не удалось обновить панель: %s", exc)


async def report_result(
    callback: CallbackQuery,
    result: CommandResult,
    air_conditioner: AirConditioner,
) -> None:
    """Единая реакция на результат команды: приписка + перерисовка панели."""
    # Отказ платы — это неверные настройки, а не пропавшая связь:
    # «плата недоступна» здесь отправило бы искать не там.
    if not result.ok and result.error == "rejected":
        note = COMMAND_REJECTED_MESSAGE
    elif not result.ok:
        note = BOARD_OFFLINE_MESSAGE
    elif result.unchanged:
        note = LIMIT_REACHED_MESSAGE.format(limit=result.state.temp)
    elif not result.ir_sent:
        note = SAVED_ONLY_MESSAGE
    else:
        note = None
    await update_menu(callback, air_conditioner, note)
