from pathlib import Path

_MESSAGES = Path(__file__).parent / "messages"


def _read(name: str) -> str:
    return (_MESSAGES / name).read_text(encoding="utf-8").strip()


MENU_MESSAGE = _read("menu_message.txt")
BOARD_OFFLINE_MESSAGE = _read("board_offline_message.txt")
COMMAND_REJECTED_MESSAGE = _read("command_rejected_message.txt")
SAVED_ONLY_MESSAGE = _read("saved_only_message.txt")
LIMIT_REACHED_MESSAGE = _read("limit_reached_message.txt")
UNCLEAR_INPUT_MESSAGE = _read("unclear_input_message.txt")
INTERNAL_ERROR_MESSAGE = _read("internal_error_message.txt")
