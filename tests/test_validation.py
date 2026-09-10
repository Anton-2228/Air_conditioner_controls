import pytest

from validation import parse_chat_ids


def test_parse_chat_ids():
    assert parse_chat_ids("123,456") == frozenset({123, 456})
    assert parse_chat_ids(" 123 , 456 ") == frozenset({123, 456})
    assert parse_chat_ids("123,,456") == frozenset({123, 456})
    assert parse_chat_ids("123") == frozenset({123})
    assert parse_chat_ids("-1001234567890") == frozenset({-1001234567890})


def test_parse_chat_ids_empty():
    assert parse_chat_ids("") == frozenset()
    assert parse_chat_ids(None) == frozenset()


def test_parse_chat_ids_rejects_garbage():
    """Лучше не подняться, чем подняться с наполовину пустым белым списком."""
    with pytest.raises(ValueError):
        parse_chat_ids("123, abc")
