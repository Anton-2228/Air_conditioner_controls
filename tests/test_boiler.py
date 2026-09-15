import pytest

from boiler import BoilerError, BoilerStatus
from commands.utils.boiler_utils import (
    CALLBACK_BOILER_OFF,
    CALLBACK_BOILER_ON,
    CALLBACK_BOILER_REFRESH,
    CALLBACK_TIMER_OPEN,
    build_boiler_keyboard,
    format_boiler_status,
    format_countdown,
    format_duration,
    parse_hh_mm,
)
from commands.utils.root_utils import CALLBACK_BACK


def test_status_parses_api_answer():
    status = BoilerStatus.from_dict(
        {"on": True, "watts": 1498.2, "volts": 227.0, "amps": 6.5, "heating": True, "countdown": 0}
    )
    assert status.on
    assert status.watts == pytest.approx(1498.2)
    assert status.heating


def test_status_survives_missing_fields():
    """Сервер может обновиться раньше бота — хендлер от этого падать не должен."""
    status = BoilerStatus.from_dict({"on": True})
    assert status.on
    assert status.watts == 0.0
    assert status.countdown == 0


def test_status_rejects_non_object():
    with pytest.raises(BoilerError):
        BoilerStatus.from_dict(["не объект"])


def test_countdown_reads_like_human_time():
    assert format_countdown(0) == "нет"
    assert format_countdown(4821) == "выключится через 1 ч 20 мин"
    assert format_countdown(600) == "выключится через 10 мин"
    assert format_countdown(7200) == "выключится через 2 ч"
    # Меньше минуты — всё ещё «1 мин», а не «0 мин».
    assert format_countdown(20) == "выключится через 1 мин"


def test_duration_reads_like_human_time():
    assert format_duration(90) == "1 ч 30 мин"
    assert format_duration(120) == "2 ч"
    assert format_duration(45) == "45 мин"


def test_panel_shows_only_on_or_off():
    """Ваттметр различает «греется» и «вода готова», но в панели этого нет:
    показываем ровно то, чем управляем, — питание."""
    on = format_boiler_status(BoilerStatus(on=True, heating=False, watts=10.7))
    assert "🟢 Включен" in on
    assert "Вт" not in on
    assert "🔴 Выключен" in format_boiler_status(BoilerStatus(on=False))


def test_panel_survives_unknown_status():
    text = format_boiler_status(None, "note")
    assert "нет данных" in text
    assert text.endswith("note")


def test_keyboard_always_has_all_buttons():
    """Розетку могут переключить кнопкой на корпусе, поэтому кнопки шлют
    конкретное состояние и работают с первого нажатия в любом случае."""
    for status in (None, BoilerStatus(on=True), BoilerStatus(on=False)):
        keyboard = build_boiler_keyboard(status)
        data = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        assert data == [
            CALLBACK_BOILER_ON,
            CALLBACK_BOILER_OFF,
            CALLBACK_TIMER_OPEN,
            CALLBACK_BOILER_REFRESH,
            CALLBACK_BACK,
        ]
        # Питание в первой строке, дальше по одной кнопке в строке.
        assert [len(row) for row in keyboard.inline_keyboard] == [2, 1, 1, 1]


def test_time_input_is_parsed_strictly():
    assert parse_hh_mm("01:30") == 90
    assert parse_hh_mm("1:30") == 90
    assert parse_hh_mm(" 00:45 ") == 45
    assert parse_hh_mm("00:00") == 0
    assert parse_hh_mm("24:00") == 24 * 60


@pytest.mark.parametrize("text", ["1:5", "90", "1.30", "1ч30", "25:00", "01:60", "", "скоро"])
def test_time_input_rejects_everything_else(text):
    """Угадывать здесь опаснее, чем переспросить: «1:5» — это опечатка,
    а не пять минут, и бойлер включится не тогда, когда ждут."""
    assert parse_hh_mm(text) is None
