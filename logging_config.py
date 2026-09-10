import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Логи уходят в stdout, чтобы их собирал docker logs."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    # aiogram на INFO сыпет каждым апдейтом, для одного пользователя это шум
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
