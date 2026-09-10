def parse_chat_ids(raw: str | None) -> frozenset[int]:
    """Разбирает ALLOWED_CHAT_IDS вида "123,456".

    Пустые куски пропускает, на мусоре падает — лучше не подняться,
    чем подняться с наполовину пустым белым списком.
    """
    if not raw:
        return frozenset()
    result = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            result.add(int(chunk))
        except ValueError as exc:
            raise ValueError(f"ALLOWED_CHAT_IDS: {chunk!r} не является числом") from exc
    return frozenset(result)
