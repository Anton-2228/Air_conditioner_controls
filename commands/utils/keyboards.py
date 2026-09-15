from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from air_conditioner import MODE_COOL, MODE_HEAT, POWER_OFF, POWER_ON, AcState

from .root_utils import add_back_button

CALLBACK_POWER_ON = "ac_power_on"
CALLBACK_POWER_OFF = "ac_power_off"
CALLBACK_MODE_COOL = "ac_mode_cool"
CALLBACK_MODE_HEAT = "ac_mode_heat"
CALLBACK_TEMP_UP = "ac_temp_up"
CALLBACK_TEMP_DOWN = "ac_temp_down"
CALLBACK_NOOP = "ac_noop"

POWER_BY_CALLBACK = {
    CALLBACK_POWER_ON: POWER_ON,
    CALLBACK_POWER_OFF: POWER_OFF,
}

MODE_BY_CALLBACK = {
    CALLBACK_MODE_COOL: MODE_COOL,
    CALLBACK_MODE_HEAT: MODE_HEAT,
}

TEMP_DELTA_BY_CALLBACK = {
    CALLBACK_TEMP_UP: 1,
    CALLBACK_TEMP_DOWN: -1,
}


def _mark(active: bool, text: str) -> str:
    return ("✅ " if active else "") + text


def build_menu_keyboard(state: AcState) -> InlineKeyboardMarkup:
    """Панель целиком: включение и выключение, два режима, стрелки температуры."""
    builder = InlineKeyboardBuilder()
    # Две кнопки вместо тумблера: каждая шлёт своё состояние, не глядя на то,
    # что бот думает о кондиционере. Если его выключили пультом, «Выключить»
    # всё равно сработает с первого нажатия.
    builder.button(
        text=_mark(state.power == POWER_ON, "🟢 Включить"),
        callback_data=CALLBACK_POWER_ON,
    )
    builder.button(
        text=_mark(state.power == POWER_OFF, "🔴 Выключить"),
        callback_data=CALLBACK_POWER_OFF,
    )
    builder.button(
        text=_mark(state.mode == MODE_COOL, "❄️ Охлаждение"),
        callback_data=CALLBACK_MODE_COOL,
    )
    builder.button(
        text=_mark(state.mode == MODE_HEAT, "🔥 Нагрев"),
        callback_data=CALLBACK_MODE_HEAT,
    )
    builder.button(text="🔽", callback_data=CALLBACK_TEMP_DOWN)
    # Средняя кнопка — просто индикатор: у inline-кнопки обязано быть действие,
    # поэтому у неё отдельный колбэк, который ничего не делает.
    builder.button(text=f"{state.temp}°C", callback_data=CALLBACK_NOOP)
    builder.button(text="🔼", callback_data=CALLBACK_TEMP_UP)
    add_back_button(builder)
    builder.adjust(2, 2, 3, 1)
    return builder.as_markup()
