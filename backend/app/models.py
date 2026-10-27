"""Plain data containers. Actuals and forecasts are deliberately separate types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

INTERVAL_MINUTES = 30


@dataclass(frozen=True)
class Actual:
    """Metered/estimated wind output for one delivery interval (FUELHH, fuelType=WIND)."""

    start: datetime  # delivery interval start, UTC
    mw: float


@dataclass(frozen=True)
class Forecast:
    """One forecast vintage for one delivery interval (WINDFOR)."""

    start: datetime  # delivery interval start, UTC
    publish: datetime  # when this forecast was published, UTC
    mw: float


@dataclass
class QualityCounts:
    """What the cleaning step saw and discarded. Nothing is silently dropped."""

    raw_records: int = 0
    ignored_other_fuel: int = 0
    null_generation: int = 0
    invalid_generation: int = 0  # non-numeric, NaN/inf, negative, implausibly large
    invalid_timestamp: int = 0  # unparseable, or not aligned to a half-hour boundary
    naive_timestamps: int = 0  # no UTC offset supplied; treated as UTC
    duplicate_records: int = 0
    conflicting_duplicates: int = 0  # duplicates whose values disagree
    valid_records: int = 0

    def as_dict(self) -> dict[str, int]:
        return dict(self.__dict__)


@dataclass
class Dataset:
    """A loaded dataset plus its provenance."""

    actuals: list[Actual] = field(default_factory=list)
    forecasts: list[Forecast] = field(default_factory=list)
    actual_quality: QualityCounts = field(default_factory=QualityCounts)
    forecast_quality: QualityCounts = field(default_factory=QualityCounts)
    # "live" = fetched from Elexon this process; "cached" = snapshot of an earlier live
    # fetch; "synthetic" = development fixtures, NOT real data.
    provenance: str = "synthetic"
    fetched_at: str | None = None
    notes: list[str] = field(default_factory=list)
