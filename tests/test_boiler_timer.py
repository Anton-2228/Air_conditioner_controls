import asyncio

import pytest

from boiler import BoilerStatus, DelayedStart
from commands.utils.boiler_utils import (
    CALLBACK_TIMER_BACK,
    CALLBACK_TIMER_CANCEL,
    CALLBACK_TIMER_NOW,
    build_timer_delay_keyboard,
    build_timer_duration_keyboard,
    format_boiler_status,
)


class FakeBoiler:
    """Розетка, которая только запоминает, что ей велели."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    async def turn_on(self, minutes: int = 0) -> None:
        self.calls.append(minutes)


def test_delay_step_offers_immediate_start_and_cancel():
    data = [b.callback_data for row in build_timer_delay_keyboard().inline_keyboard for b in row]
    assert data == [CALLBACK_TIMER_NOW, CALLBACK_TIMER_CANCEL]


def test_duration_step_offers_back_and_cancel():
    data = [b.callback_data for row in build_timer_duration_keyboard().inline_keyboard for b in row]
    assert data == [CALLBACK_TIMER_BACK, CALLBACK_TIMER_CANCEL]


async def test_delayed_start_turns_on_with_duration():
    boiler = FakeBoiler()
    scheduler = DelayedStart(boiler)
    scheduler.schedule(delay_minutes=0, duration_minutes=90)
    await asyncio.sleep(0.05)
    # Длительность уходит в саму розетку: выключит она, а не бот.
    assert boiler.calls == [90]
    assert scheduler.plan is None


async def test_cancel_stops_pending_start():
    boiler = FakeBoiler()
    scheduler = DelayedStart(boiler)
    scheduler.schedule(delay_minutes=0, duration_minutes=90)
    assert scheduler.cancel() is True
    await asyncio.sleep(0.05)
    assert boiler.calls == []
    assert scheduler.plan is None
    # Отменять нечего — и это не ошибка, кнопки питания жмут и без таймера.
    assert scheduler.cancel() is False


async def test_new_plan_replaces_the_old_one():
    """Два плана на одно устройство означали бы, что кто-то из них ошибётся."""
    boiler = FakeBoiler()
    scheduler = DelayedStart(boiler)
    scheduler.schedule(delay_minutes=60, duration_minutes=30)
    scheduler.schedule(delay_minutes=0, duration_minutes=15)
    await asyncio.sleep(0.05)
    assert boiler.calls == [15]


@pytest.mark.parametrize("on", [True, False])
async def test_panel_shows_planned_start_instead_of_countdown(on):
    boiler = FakeBoiler()
    scheduler = DelayedStart(boiler)
    scheduler.schedule(delay_minutes=90, duration_minutes=120)
    text = format_boiler_status(BoilerStatus(on=on, countdown=0), plan=scheduler.plan)
    assert "включится через 1 ч 30 мин на 2 ч" in text
    scheduler.cancel()


async def test_panel_falls_back_to_socket_countdown():
    text = format_boiler_status(BoilerStatus(on=True, countdown=4821), plan=None)
    assert "выключится через 1 ч 20 мин" in text
