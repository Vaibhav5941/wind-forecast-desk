"""Forecast-vintage selection: what did the buyer know at decision time?

A "vintage" is one published forecast for a given delivery interval. For each target
interval we pick the LATEST vintage with publish_time <= cutoff. Anything published after
the cutoff is excluded - it was not available when the decision had to be made.

Two ways to define the cutoff:

* ``DayAheadCutoff``  - one cutoff per delivery day: (delivery local date - lead_days) at
  a wall-clock time in a timezone (default: previous day 09:00 Europe/London).
  This is an ASSUMPTION, not an Elexon-documented value. See README.
* ``HorizonCutoff``   - a fixed lead time before each interval (e.g. 24h). Useful for
  inspecting earlier or later vintages.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from .models import Forecast


class CutoffRule(Protocol):
    def cutoff_for(self, target_start: datetime) -> datetime: ...

    def describe(self) -> str: ...


@dataclass(frozen=True)
class DayAheadCutoff:
    tz: str = "Europe/London"
    clock: str = "09:00"  # HH:MM local wall-clock time
    lead_days: int = 1

    def _time(self) -> time:
        hh, mm = self.clock.split(":")
        return time(int(hh), int(mm))

    def cutoff_for(self, target_start: datetime) -> datetime:
        zone = ZoneInfo(self.tz)
        local_day: date = target_start.astimezone(zone).date()
        cutoff_day = local_day - timedelta(days=self.lead_days)
        naive = datetime.combine(cutoff_day, self._time())
        # Round-trip through UTC so a wall-clock time that doesn't exist (DST gap) is normalised.
        aware = naive.replace(tzinfo=zone)
        return aware.astimezone(UTC)

    def describe(self) -> str:
        day = "the day before" if self.lead_days == 1 else f"{self.lead_days} days before"
        if self.lead_days == 0:
            day = "the same day as"
        return f"{self.clock} {self.tz} {day} delivery (assumption)"


@dataclass(frozen=True)
class HorizonCutoff:
    hours: float

    def cutoff_for(self, target_start: datetime) -> datetime:
        return target_start - timedelta(hours=self.hours)

    def describe(self) -> str:
        return f"{self.hours:g} h before each delivery interval"


@dataclass(frozen=True)
class Selection:
    target_start: datetime
    cutoff: datetime
    forecast: Forecast | None
    n_eligible: int  # vintages published at/before cutoff
    n_excluded_after_cutoff: int  # vintages published after cutoff (not used)


def index_forecasts(forecasts: list[Forecast]) -> dict[datetime, list[Forecast]]:
    """Group by delivery interval, each list sorted by publish time ascending."""
    grouped: dict[datetime, list[Forecast]] = defaultdict(list)
    for f in forecasts:
        grouped[f.start].append(f)
    for lst in grouped.values():
        lst.sort(key=lambda f: f.publish)
    return grouped


def select_vintage(vintages: list[Forecast], cutoff: datetime) -> Forecast | None:
    """Latest vintage with publish <= cutoff (inclusive). `vintages` sorted by publish."""
    pubs = [v.publish for v in vintages]
    i = bisect_right(pubs, cutoff)
    return vintages[i - 1] if i > 0 else None


def select_for_targets(
    index: dict[datetime, list[Forecast]],
    targets: list[datetime],
    rule: CutoffRule,
) -> dict[datetime, Selection]:
    out: dict[datetime, Selection] = {}
    for t in targets:
        cutoff = rule.cutoff_for(t)
        vintages = index.get(t, [])
        chosen = select_vintage(vintages, cutoff)
        n_eligible = sum(1 for v in vintages if v.publish <= cutoff)
        out[t] = Selection(
            target_start=t,
            cutoff=cutoff,
            forecast=chosen,
            n_eligible=n_eligible,
            n_excluded_after_cutoff=len(vintages) - n_eligible,
        )
    return out
