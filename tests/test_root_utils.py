from air_conditioner import AcState
from commands.utils.boiler_utils import build_boiler_keyboard
from commands.utils.keyboards import build_menu_keyboard
from commands.utils.root_utils import (
    CALLBACK_BACK,
    CALLBACK_OPEN_AC,
    CALLBACK_OPEN_BOILER,
    build_root_keyboard,
)


def test_root_offers_both_devices():
    rows = build_root_keyboard(with_boiler=True).inline_keyboard
    data = [button.callback_data for row in rows for button in row]
    assert data == [CALLBACK_OPEN_AC, CALLBACK_OPEN_BOILER]


def test_root_hides_boiler_when_not_configured():
    """Кнопка, ведущая в «не настроено», хуже отсутствующей кнопки."""
    rows = build_root_keyboard(with_boiler=False).inline_keyboard
    data = [button.callback_data for row in rows for button in row]
    assert data == [CALLBACK_OPEN_AC]


def test_both_panels_have_a_way_back():
    """Из панели устройства должен быть выход, иначе /menu — единственный
    способ вернуться, а он плодит новые сообщения в чате."""
    for keyboard in (build_menu_keyboard(AcState()), build_boiler_keyboard(None)):
        data = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        assert data.count(CALLBACK_BACK) == 1
        assert data[-1] == CALLBACK_BACK  # последняя кнопка, а не посреди панели
