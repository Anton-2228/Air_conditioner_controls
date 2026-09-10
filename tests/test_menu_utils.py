import asyncio

from aiogram.types import CallbackQuery

from air_conditioner import AcState, CommandResult
from commands.utils.keyboards import (
    CALLBACK_MODE_COOL,
    CALLBACK_POWER_TOGGLE,
    CALLBACK_TEMP_DOWN,
    CALLBACK_TEMP_UP,
    build_menu_keyboard,
)
from commands.utils.menu_utils import ack_callback, format_status
from datafiles import BOARD_OFFLINE_MESSAGE, LIMIT_REACHED_MESSAGE, SAVED_ONLY_MESSAGE


def make_callback(data: str) -> CallbackQuery:
    return CallbackQuery(
        id="1",
        from_user={"id": 1, "is_bot": False, "first_name": "x"},
        chat_instance="ci",
        data=data,
    )


async def test_ack_callback_survives_aiogram_return_type():
    """callback.answer() возвращает объект метода API, а не корутину.

    asyncio.create_task такое не принимает и падает с TypeError, а падение
    в хендлере доходит до пользователя как «что-то пошло не так».
    """
    ack_callback(make_callback(CALLBACK_TEMP_UP))
    # Даём задаче стартовать: без бота она завершится ошибкой, но эта
    # ошибка должна остаться в логах, а не вылететь в хендлер.
    await asyncio.sleep(0)


def test_status_shows_everything_when_off():
    text = format_status(AcState(power="Off", mode="Cool", temp=24), True)
    assert "🔴 Выключен" in text
    assert "❄️ Охлаждение" in text
    assert "24" in text
    assert "🟢 на связи" in text


def test_status_marks_unknown_board():
    assert "⏳" in format_status(AcState(), None)
    assert "🔴 недоступна" in format_status(AcState(), False)


def test_note_is_appended_not_replacing_status():
    text = format_status(AcState(temp=25), False, BOARD_OFFLINE_MESSAGE)
    assert BOARD_OFFLINE_MESSAGE in text
    assert "25" in text  # статус на месте, приписка его не вытеснила


def test_notes_are_formattable():
    assert "30" in LIMIT_REACHED_MESSAGE.format(limit=30)
    assert SAVED_ONLY_MESSAGE  # не пустой


def test_keyboard_toggles_power_label():
    off = build_menu_keyboard(AcState(power="Off"))
    on = build_menu_keyboard(AcState(power="On"))
    assert "Включить" in off.inline_keyboard[0][0].text
    assert "Выключить" in on.inline_keyboard[0][0].text
    assert off.inline_keyboard[0][0].callback_data == CALLBACK_POWER_TOGGLE


def test_keyboard_has_arrows_around_value():
    rows = build_menu_keyboard(AcState(temp=22)).inline_keyboard
    down, value, up = rows[2]
    assert down.callback_data == CALLBACK_TEMP_DOWN
    assert up.callback_data == CALLBACK_TEMP_UP
    assert "22" in value.text


def test_keyboard_marks_active_mode():
    rows = build_menu_keyboard(AcState(mode="Cool")).inline_keyboard
    cool, heat = rows[1]
    assert cool.callback_data == CALLBACK_MODE_COOL
    assert "✅" in cool.text
    assert "✅" not in heat.text


def test_every_button_has_a_callback():
    """Кнопка без действия молча ничего не делает — легко не заметить."""
    for row in build_menu_keyboard(AcState()).inline_keyboard:
        for button in row:
            assert button.callback_data


def test_result_notes_cover_every_branch():
    state = AcState(temp=30)
    assert CommandResult(ok=False, ir_sent=False, state=state, error="offline").ok is False
    assert CommandResult(ok=True, ir_sent=False, state=state, unchanged=True).unchanged is True
    assert CommandResult(ok=True, ir_sent=True, state=state).unchanged is False
