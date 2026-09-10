import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)


class WhitelistMiddleware(BaseMiddleware):
    """Пропускает только разрешённые chat_id. Остальных игнорирует молча.

    Ответ «доступ запрещён» подтвердил бы постороннему, что бот живой,
    поэтому чужой апдейт просто не обрабатывается.
    """

    def __init__(self, allowed_chat_ids: frozenset[int]) -> None:
        self.allowed_chat_ids = allowed_chat_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat_id = self._extract_chat_id(event)
        if chat_id not in self.allowed_chat_ids:
            logger.warning(
                "Запрос от неразрешённого chat_id=%s (%s), игнорирую",
                chat_id,
                type(event).__name__,
            )
            return None
        return await handler(event, data)

    @staticmethod
    def _extract_chat_id(event: TelegramObject) -> int | None:
        if isinstance(event, Message):
            return event.chat.id
        if isinstance(event, CallbackQuery):
            if event.message is not None:
                return event.message.chat.id
            return event.from_user.id if event.from_user else None
        return None
