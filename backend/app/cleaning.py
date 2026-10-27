"""Validation and de-duplication of raw Elexon records.

Rules:
* Records that are null or invalid are COUNTED and EXCLUDED. They are never turned into 0 MW.
* Timestamps are normalised to UTC. Elexon `startTime` / `publishTime` are expected to be
  ISO-8601 with a `Z` suffix; naive values are treated as UTC and counted.
* Only half-hour-aligned delivery intervals are accepted.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from .models import Actual, Forecast, QualityCounts

# GB wind capacity is well under this; anything above is treated as a data fault.
MAX_PLAUSIBLE_MW = 60_000.0


def parse_ts(value: Any, counts: QualityCounts | None = None) -> datetime | None:
    """Parse an ISO-8601 timestamp to an aware UTC datetime, or None if unusable."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        if counts is not None:
            counts.naive_timestamps += 1
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _is_half_hour_aligned(dt: datetime) -> bool:
    return dt.minute in (0, 30) and dt.second == 0 and dt.microsecond == 0


def parse_generation(value: Any) -> tuple[float | None, str | None]:
    """Return (mw, problem). problem is None, 'null' or 'invalid'."""
    if value is None:
        return None, "null"
    if isinstance(value, bool):
        return None, "invalid"
    try:
        mw = float(value)
    except (TypeError, ValueError):
        return None, "invalid"
    if math.isnan(mw) or math.isinf(mw) or mw < 0 or mw > MAX_PLAUSIBLE_MW:
        return None, "invalid"
    return mw, None


def clean_actuals(raw: Iterable[dict[str, Any]]) -> tuple[list[Actual], QualityCounts]:
    counts = QualityCounts()
    # start -> (publish_or_None, mw)
    kept: dict[datetime, tuple[datetime | None, float]] = {}
    for rec in raw:
        counts.raw_records += 1
        fuel = str(rec.get("fuelType", "")).upper()
        if fuel != "WIND":
            counts.ignored_other_fuel += 1
            continue
        start = parse_ts(rec.get("startTime"), counts)
        if start is None or not _is_half_hour_aligned(start):
            counts.invalid_timestamp += 1
            continue
        mw, problem = parse_generation(rec.get("generation"))
        if problem == "null":
            counts.null_generation += 1
            continue
        if problem == "invalid":
            counts.invalid_generation += 1
            continue
        assert mw is not None
        publish = parse_ts(rec.get("publishTime"))
        if start in kept:
            counts.duplicate_records += 1
            prev_pub, prev_mw = kept[start]
            if prev_mw != mw:
                counts.conflicting_duplicates += 1
            # Keep the most recently published value; if publish time is unknown, keep the later row.
            if prev_pub is not None and publish is not None and publish < prev_pub:
                continue
        kept[start] = (publish, mw)
    actuals = [Actual(start=s, mw=v[1]) for s, v in sorted(kept.items())]
    counts.valid_records = len(actuals)
    return actuals, counts


def clean_forecasts(raw: Iterable[dict[str, Any]]) -> tuple[list[Forecast], QualityCounts]:
    counts = QualityCounts()
    kept: dict[tuple[datetime, datetime], float] = {}
    for rec in raw:
        counts.raw_records += 1
        start = parse_ts(rec.get("startTime"), counts)
        publish = parse_ts(rec.get("publishTime"), counts)
        if start is None or publish is None or not _is_half_hour_aligned(start):
            counts.invalid_timestamp += 1
            continue
        mw, problem = parse_generation(rec.get("generation"))
        if problem == "null":
            counts.null_generation += 1
            continue
        if problem == "invalid":
            counts.invalid_generation += 1
            continue
        assert mw is not None
        key = (start, publish)
        if key in kept:
            counts.duplicate_records += 1
            if kept[key] != mw:
                counts.conflicting_duplicates += 1
        kept[key] = mw
    forecasts = [Forecast(start=s, publish=p, mw=v) for (s, p), v in sorted(kept.items())]
    counts.valid_records = len(forecasts)
    return forecasts, counts
