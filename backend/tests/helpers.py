"""Tiny builders for test data. All values here are invented test inputs, not real data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Actual, Forecast


def utc(day: int, hh: int = 0, mm: int = 0, month: int = 1) -> datetime:
    return datetime(2026, month, day, hh, mm, tzinfo=UTC)


def fc(start: datetime, publish: datetime, mw: float) -> Forecast:
    return Forecast(start=start, publish=publish, mw=mw)


def act(start: datetime, mw: float) -> Actual:
    return Actual(start=start, mw=mw)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def half_hours(start: datetime, n: int) -> list[datetime]:
    return [start + timedelta(minutes=30 * i) for i in range(n)]
