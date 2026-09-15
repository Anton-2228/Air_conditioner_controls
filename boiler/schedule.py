"""Отложенный запуск бойлера.

Розетка умеет отсчитывать только автовыключение: «включить через час»
она не умеет, поэтому паузу до включения отсчитывает бот. А вот
длительность нагрева уходит в саму розетку, и она доведёт дело до конца,
даже если бот к тому моменту умрёт.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .boiler import Boiler
from .models import BoilerError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Plan:
    """Запланированное включение."""

    start_at: datetime
    duration_minutes: int

    @property
    def seconds_left(self) -> int:
        return max(0, int((self.start_at - datetime.now(UTC)).total_seconds()))


class DelayedStart:
    """Одно отложенное включение на всю розетку.

    Больше одного не нужно: устройство одно, и два плана на него
    означали бы, что кто-то из двоих ошибётся. Новый план отменяет старый.

    План живёт в памяти процесса: перезапуск бота его теряет. Поэтому
    в саму розетку уходит длительность нагрева — то, что важнее.
    """

    def __init__(self, boiler: Boiler) -> None:
        self._boiler = boiler
        self._task: asyncio.Task | None = None
        self._plan: Plan | None = None

    @property
    def plan(self) -> Plan | None:
        return self._plan

    def schedule(self, delay_minutes: int, duration_minutes: int) -> Plan:
        self.cancel()
        plan = Plan(
            start_at=datetime.now(UTC) + timedelta(minutes=delay_minutes),
            duration_minutes=duration_minutes,
        )
        self._plan = plan
        self._task = asyncio.create_task(self._run(delay_minutes * 60, duration_minutes))
        logger.info("Бойлер включится в %s на %s минут", plan.start_at, duration_minutes)
        return plan

    def cancel(self) -> bool:
        """Отменяет запланированное включение. True — было что отменять."""
        if self._task is None:
            return False
        self._task.cancel()
        self._task = None
        self._plan = None
        logger.info("Отложенное включение отменено")
        return True

    async def _run(self, delay_seconds: float, duration_minutes: int) -> None:
        try:
            await asyncio.sleep(delay_seconds)
            await self._boiler.turn_on(duration_minutes)
            logger.info("Отложенное включение сработало: %s минут нагрева", duration_minutes)
        except asyncio.CancelledError:
            raise
        except BoilerError as exc:
            # Сказать пользователю некому: панель давно не на экране.
            # Остаётся лог и то, что состояние он увидит по «Обновить».
            logger.warning("Отложенное включение не сработало: %s", exc)
        finally:
            # Чистим только свой план: пока мы спали, его могли заменить.
            if self._task is asyncio.current_task():
                self._task = None
                self._plan = None
