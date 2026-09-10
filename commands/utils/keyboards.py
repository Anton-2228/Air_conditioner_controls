from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from air_conditioner import MODE_COOL, MODE_HEAT, POWER_OFF, AcState

CALLBACK_POWER_TOGGLE = "ac_power_toggle"
CALLBACK_MODE_COOL = "ac_mode_cool"
CALLBACK_MODE_HEAT = "ac_mode_heat"
CALLBACK_TEMP_UP = "ac_temp_up"
CALLBACK_TEMP_DOWN = "ac_temp_down"
CALLBACK_NOOP = "ac_noop"

MODE_BY_CALLBACK = {
    CALLBACK_MODE_COOL: MODE_COOL,
    CALLBACK_MODE_HEAT: MODE_HEAT,
}

TEMP_DELTA_BY_CALLBACK = {
    CALLBACK_TEMP_UP: 1,
    CALLBACK_TEMP_DOWN: -1,
}


def build_menu_keyboard(state: AcState) -> InlineKeyboardMarkup:
    """Панель целиком: тумблер питания, два режима, стрелки температуры."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🟢 Включить" if state.power == POWER_OFF else "🔴 Выключить",
        callback_data=CALLBACK_POWER_TOGGLE,
    )
    builder.button(
        text=("✅ " if state.mode == MODE_COOL else "") + "❄️ Охлаждение",
        callback_data=CALLBACK_MODE_COOL,
    )
    builder.button(
        text=("✅ " if state.mode == MODE_HEAT else "") + "🔥 Нагрев",
        callback_data=CALLBACK_MODE_HEAT,
    )
    builder.button(text="🔽", callback_data=CALLBACK_TEMP_DOWN)
    # Средняя кнопка — просто индикатор: у inline-кнопки обязано быть действие,
    # поэтому у неё отдельный колбэк, который ничего не делает.
    builder.button(text=f"{state.temp}°C", callback_data=CALLBACK_NOOP)
    builder.button(text="🔼", callback_data=CALLBACK_TEMP_UP)
    builder.adjust(1, 2, 3)
    return builder.as_markup()
