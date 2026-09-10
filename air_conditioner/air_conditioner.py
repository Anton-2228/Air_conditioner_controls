import asyncio
import logging
from dataclasses import dataclass, replace

from .models import POWER_OFF, POWER_ON, AcState, now_iso
from .payload import build_hvac_payload
from .protocol import AcProtocol
from .state_storage import StateStorage

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    ok: bool
    """Операция завершилась успешно и состояние сохранено."""
    ir_sent: bool
    """Реально ли уходила ИК-команда (при выключенном кондиционере — нет)."""
    state: AcState
    """Актуальное состояние после операции. При ok=False — прежнее."""
    error: str | None = None
    """not_connected | offline | no_ack"""
    unchanged: bool = False
    """Менять было нечего: температура уже упёрлась в границу диапазона."""


class AirConditioner:
    """Единственная точка изменения состояния кондиционера."""

    def __init__(self, storage: StateStorage, mqtt, protocol: AcProtocol | None = None) -> None:
        self._storage = storage
        self._mqtt = mqtt
        self._protocol = protocol or AcProtocol()
        self._state = storage.load()
        self._lock = asyncio.Lock()
        logger.info("Стартовое состояние: %s", self._state)

    def get_state(self) -> AcState:
        return self._state

    @property
    def board_online(self) -> bool | None:
        """None — пока не знаем (не пришёл LWT)."""
        return self._mqtt.board_online

    async def toggle_power(self, chat_id: int) -> CommandResult:
        new_power = POWER_OFF if self._state.power == POWER_ON else POWER_ON
        return await self._apply({"power": new_power}, chat_id, force_send=True)

    async def set_mode(self, mode: str, chat_id: int) -> CommandResult:
        return await self._apply({"mode": mode}, chat_id, force_send=False)

    async def set_temperature(self, temp: int, chat_id: int) -> CommandResult:
        return await self._apply({"temp": temp}, chat_id, force_send=False)

    async def step_temperature(self, delta: int, chat_id: int) -> CommandResult:
        """Сдвигает температуру на delta градусов, не выходя за диапазон протокола.

        Если уже на границе — ничего не отправляет и не пишет на диск.
        """
        target = self._state.temp + delta
        if not self._protocol.in_range(target):
            return CommandResult(ok=True, ir_sent=False, state=self._state, unchanged=True)
        return await self._apply({"temp": target}, chat_id, force_send=False)

    async def _apply(self, changes: dict, chat_id: int, force_send: bool) -> CommandResult:
        # Лок держится на весь цикл «прочитать — изменить — отправить — записать»,
        # включая ожидание подтверждения (до ~5 с). Это верно: устройство одно,
        # параллельные ИК-посылки бессмысленны, второй пользователь подождёт.
        async with self._lock:
            candidate = replace(
                self._state,
                **changes,
                updated_at=now_iso(),
                updated_by=chat_id,
            )
            # Правка режима или температуры при выключенном кондиционере
            # только запоминается: ИК-команда с Power=Off ничего бы не сделала.
            need_ir = force_send or candidate.power == POWER_ON

            if need_ir:
                sent = await self._mqtt.send_hvac(build_hvac_payload(candidate, self._protocol))
                if not sent:
                    logger.warning(
                        "Команда %s не отправлена (%s), состояние не меняю",
                        changes,
                        self._mqtt.last_error,
                    )
                    return CommandResult(
                        ok=False,
                        ir_sent=False,
                        state=self._state,
                        error=self._mqtt.last_error,
                    )

            self._state = candidate
            self._storage.save(candidate)
            logger.info("Состояние обновлено: %s (ИК отправлен: %s)", candidate, need_ir)
            return CommandResult(ok=True, ir_sent=need_ir, state=candidate)
