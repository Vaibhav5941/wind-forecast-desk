"""SYNTHETIC development fixtures. NOT REAL ELEXON DATA.

Generates raw records in the same shape the Elexon client returns, so they pass through the
exact same cleaning/vintage/matching code. Deliberately includes a few gaps, nulls, duplicates
and an invalid value so the data-quality paths are exercised. Output is labelled
``provenance="synthetic"`` everywhere and is never written to the snapshot directory.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta
from typing import Any

SYNTHETIC_SEED = 20260101


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate(
    lo: datetime, hi: datetime, seed: int = SYNTHETIC_SEED
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(seed)
    step = timedelta(minutes=30)
    targets: list[datetime] = []
    t = lo
    while t < hi:
        targets.append(t)
        t += step

    # Smooth "truth": slow weather regime + diurnal wobble + noise (MW)
    truth: dict[datetime, float] = {}
    level = 8000.0
    for t in targets:
        level += rng.gauss(0, 120)
        level = min(max(level, 600.0), 19000.0)
        wobble = 600 * math.sin(t.hour / 24 * 2 * math.pi)
        truth[t] = max(0.0, level + wobble + rng.gauss(0, 150))

    actual_raw: list[dict[str, Any]] = []
    for i, t in enumerate(targets):
        if i % 997 == 500:  # missing interval (no record at all)
            continue
        gen: Any = round(truth[t])
        if i % 1301 == 700:
            gen = None  # null generation
        if i % 1499 == 900:
            gen = -50  # invalid negative
        rec = {
            "dataset": "FUELHH",
            "publishTime": _iso(t + timedelta(minutes=30)),
            "startTime": _iso(t),
            "fuelType": "WIND",
            "generation": gen,
        }
        actual_raw.append(rec)
        if i % 701 == 100:
            actual_raw.append(dict(rec))  # exact duplicate
    # a non-wind row, which must be ignored
    actual_raw.append(
        {
            "dataset": "FUELHH",
            "startTime": _iso(lo),
            "publishTime": _iso(lo),
            "fuelType": "CCGT",
            "generation": 9000,
        }
    )

    forecast_raw: list[dict[str, Any]] = []
    for i, t in enumerate(targets):
        # vintages published every 3 h, from 4 days before to 6 h after delivery
        # (the post-delivery ones exist to prove they are excluded by the cutoff rule)
        first = t - timedelta(days=4)
        pub = first.replace(minute=0)
        while pub <= t + timedelta(hours=6):
            horizon_h = max((t - pub).total_seconds() / 3600, 0)
            sigma = 150 + 28 * horizon_h  # error grows with lead time
            val = max(0.0, truth[t] + rng.gauss(0, sigma))
            forecast_raw.append(
                {
                    "dataset": "WINDFOR",
                    "publishTime": _iso(pub),
                    "startTime": _iso(t),
                    "generation": None if (i % 1777 == 300 and pub.hour == 6) else round(val),
                }
            )
            pub += timedelta(hours=3)
    return actual_raw, forecast_raw


def utc(y: int, m: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=UTC)
