"""Runtime configuration, read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Data mode:
    #   auto      -> snapshot if present, else live (and cache it), else synthetic if allowed
    #   live      -> always call Elexon (result is still cached to a snapshot)
    #   snapshot  -> only use an existing snapshot file
    #   synthetic -> only use clearly-labelled synthetic fixtures
    data_mode: str = "auto"
    allow_synthetic_fallback: bool = True

    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    elexon_timeout_s: float = 30.0
    elexon_retries: int = 3
    # Query parameter names are configurable because they could not be verified
    # against the live documentation from the build environment.
    elexon_from_param: str = "publishDateTimeFrom"
    elexon_to_param: str = "publishDateTimeTo"
    elexon_chunk_days: int = 3
    # WINDFOR forecasts for January delivery are published before January starts.
    forecast_lookback_days: int = 7

    snapshot_dir: Path = Path("data/snapshots")

    # Allowed analysis window (inclusive dates)
    period_start: date = date(2026, 1, 1)
    period_end: date = date(2026, 1, 31)

    # Decision-cutoff defaults (ASSUMPTION - see README)
    cutoff_timezone: str = "Europe/London"
    cutoff_time: str = "09:00"
    cutoff_lead_days: int = 1

    # Below this coverage, metrics are flagged as not authoritative.
    min_authoritative_coverage: float = 0.95

    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    static_dir: Path | None = None


def load_settings() -> Settings:
    cors = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    static = os.getenv("STATIC_DIR")
    return Settings(
        data_mode=os.getenv("DATA_MODE", "auto").strip().lower(),
        allow_synthetic_fallback=_bool("ALLOW_SYNTHETIC_FALLBACK", True),
        elexon_base_url=os.getenv("ELEXON_BASE_URL", Settings.elexon_base_url).rstrip("/"),
        elexon_timeout_s=float(os.getenv("ELEXON_TIMEOUT_S", "30")),
        elexon_retries=int(os.getenv("ELEXON_RETRIES", "3")),
        elexon_from_param=os.getenv("ELEXON_FROM_PARAM", Settings.elexon_from_param),
        elexon_to_param=os.getenv("ELEXON_TO_PARAM", Settings.elexon_to_param),
        elexon_chunk_days=int(os.getenv("ELEXON_CHUNK_DAYS", "3")),
        forecast_lookback_days=int(os.getenv("FORECAST_LOOKBACK_DAYS", "7")),
        snapshot_dir=Path(os.getenv("SNAPSHOT_DIR", "data/snapshots")),
        cutoff_timezone=os.getenv("CUTOFF_TIMEZONE", "Europe/London"),
        cutoff_time=os.getenv("CUTOFF_TIME", "09:00"),
        cutoff_lead_days=int(os.getenv("CUTOFF_LEAD_DAYS", "1")),
        min_authoritative_coverage=float(os.getenv("MIN_AUTHORITATIVE_COVERAGE", "0.95")),
        cors_origins=[o.strip() for o in cors.split(",") if o.strip()],
        static_dir=Path(static) if static else None,
    )
