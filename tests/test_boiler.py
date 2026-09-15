import pytest

from boiler import STATE_HEATING, STATE_OFF, STATE_READY, BoilerError, BoilerStatus
from commands.utils.boiler_utils import (
    CALLBACK_BOILER_OFF,
    CALLBACK_BOILER_ON,
    CALLBACK_BOILER_REFRESH,
    build_boiler_keyboard,
    format_boiler_status,
    format_countdown,
    format_watts,
)
from commands.utils.root_utils import CALLBACK_BACK


def test_status_parses_api_answer():
    status = BoilerStatus.from_dict(
        {"on": True, "watts": 1498.2, "volts": 227.0, "amps": 6.5, "heating": True, "countdown": 0}
    )
    assert status.on
    assert status.watts == pytest.approx(1498.2)
    assert status.state == STATE_HEATING


def test_status_survives_missing_fields():
    """Сервер может обновиться раньше бота — хендлер от этого падать не должен."""
    status = BoilerStatus.from_dict({"on": True})
    assert status.state == STATE_READY
    assert status.watts == 0.0
    assert status.countdown == 0


def test_power_on_without_heating_is_ready_not_error():
    """Термостат снял нагрузку — значит вода нагрета, а не что-то сломалось."""
    assert BoilerStatus(on=True, heating=False).state == STATE_READY
    assert BoilerStatus(on=False, heating=False).state == STATE_OFF


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


def test_panel_shows_watts_in_every_state():
    heating = format_boiler_status(BoilerStatus(on=True, heating=True, watts=1498.2))
    assert "1498 Вт" in heating
    # Вода готова: ТЭН отключён термостатом, но электроника под напряжением.
    ready = format_boiler_status(BoilerStatus(on=True, heating=False, watts=10.7))
    assert "10,7 Вт" in ready
    assert "Вода готова" in ready
    assert "0 Вт" in format_boiler_status(BoilerStatus(on=False, watts=0.0))


def test_watts_keep_tenths_only_on_small_numbers():
    # На малых числах округление до целого стёрло бы разницу между
    # «стоит под напряжением» и «выключен».
    assert format_watts(10.7) == "10,7 Вт"
    assert format_watts(0.2) == "0,2 Вт"
    assert format_watts(0.0) == "0 Вт"
    assert format_watts(1498.2) == "1498 Вт"


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
            CALLBACK_BOILER_REFRESH,
            CALLBACK_BACK,
        ]
        # Питание в первой строке, навигация во второй.
        assert [len(row) for row in keyboard.inline_keyboard] == [2, 2]
