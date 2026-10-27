"""Loads the period's dataset once and serves it from memory.

The frontend never triggers an Elexon request on redraw: requests are answered from the
in-memory dataset, which is built from (in order of preference, depending on DATA_MODE):
a gzipped snapshot of an earlier live fetch, a fresh live fetch (then snapshotted), or -
only if allowed - clearly labelled synthetic fixtures.
"""

from __future__ import annotations

import gzip
import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import synthetic
from .analysis import local_day_window
from .cleaning import clean_actuals, clean_forecasts
from .config import Settings
from .elexon import ElexonClient, ElexonError
from .models import Dataset

VALID_MODES = {"auto", "live", "snapshot", "synthetic"}


class DataUnavailable(Exception):
    """No usable dataset could be produced under the configured DATA_MODE."""


class DataStore:
    def __init__(self, settings: Settings, client_factory: Callable[[], ElexonClient] | None = None):
        if settings.data_mode not in VALID_MODES:
            raise ValueError(f"DATA_MODE must be one of {sorted(VALID_MODES)}")
        self.s = settings
        self._client_factory = client_factory or (lambda: ElexonClient(settings))
        self._lock = threading.Lock()
        self._dataset: Dataset | None = None

    # -- public -------------------------------------------------------------------------
    @property
    def snapshot_path(self) -> Path:
        tag = f"{self.s.period_start:%Y-%m}"
        return self.s.snapshot_dir / f"elexon_wind_{tag}.json.gz"

    def get(self) -> Dataset:
        with self._lock:
            if self._dataset is None:
                self._dataset = self._load()
            return self._dataset

    def refresh(self) -> Dataset:
        """Force a live fetch and rewrite the snapshot (used by the CLI)."""
        with self._lock:
            self._dataset = self._fetch_live()
            return self._dataset

    def loaded_provenance(self) -> str | None:
        return self._dataset.provenance if self._dataset else None

    # -- internals ----------------------------------------------------------------------
    def _windows(self) -> tuple[datetime, datetime, datetime, datetime]:
        lo, hi = local_day_window(self.s.period_start, self.s.period_end, self.s.cutoff_timezone)
        return (
            lo - timedelta(days=1),
            hi + timedelta(days=1),
            lo - timedelta(days=self.s.forecast_lookback_days),
            hi,
        )

    def _load(self) -> Dataset:
        mode = self.s.data_mode
        if mode == "synthetic":
            return self._synthetic("DATA_MODE=synthetic")
        if mode == "live":
            return self._fetch_live()
        if self.snapshot_path.exists():
            return self._read_snapshot()
        if mode == "snapshot":
            raise DataUnavailable(
                f"DATA_MODE=snapshot but no snapshot exists at {self.snapshot_path}. "
                "Run `python -m app.cli fetch` with network access to Elexon first."
            )
        try:  # auto
            return self._fetch_live()
        except ElexonError as exc:
            if self.s.allow_synthetic_fallback:
                return self._synthetic(f"live Elexon fetch failed: {exc}")
            raise DataUnavailable(f"Live Elexon fetch failed and synthetic fallback is off: {exc}") from exc

    def _fetch_live(self) -> Dataset:
        a_lo, a_hi, f_lo, f_hi = self._windows()
        client = self._client_factory()
        actual_raw = client.fetch_wind_actuals(a_lo, a_hi)
        forecast_raw = client.fetch_wind_forecasts(f_lo, f_hi)
        fetched_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._write_snapshot(actual_raw, forecast_raw, fetched_at)
        return self._build(actual_raw, forecast_raw, "live", fetched_at, [])

    def _write_snapshot(self, actual_raw: list, forecast_raw: list, fetched_at: str) -> None:
        self.s.snapshot_dir.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "meta": {
                "fetched_at": fetched_at,
                "source": self.s.elexon_base_url,
                "datasets": ["FUELHH (fuelType=WIND)", "WINDFOR"],
                "period": [self.s.period_start.isoformat(), self.s.period_end.isoformat()],
                "synthetic": False,
            },
            "actuals_raw": actual_raw,
            "forecasts_raw": forecast_raw,
        }
        tmp = self.snapshot_path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump(payload, fh)
        tmp.replace(self.snapshot_path)

    def _read_snapshot(self) -> Dataset:
        with gzip.open(self.snapshot_path, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        meta = payload.get("meta", {})
        if meta.get("synthetic"):
            raise DataUnavailable("Refusing to treat a synthetic snapshot as real data.")
        return self._build(
            payload["actuals_raw"], payload["forecasts_raw"], "cached", meta.get("fetched_at"), []
        )

    def _synthetic(self, reason: str) -> Dataset:
        lo, hi = local_day_window(self.s.period_start, self.s.period_end, self.s.cutoff_timezone)
        actual_raw, forecast_raw = synthetic.generate(lo, hi)
        return self._build(
            actual_raw,
            forecast_raw,
            "synthetic",
            None,
            [f"SYNTHETIC DEVELOPMENT DATA - not Elexon data. Reason: {reason}"],
        )

    @staticmethod
    def _build(actual_raw, forecast_raw, provenance, fetched_at, notes) -> Dataset:
        actuals, aq = clean_actuals(actual_raw)
        forecasts, fq = clean_forecasts(forecast_raw)
        return Dataset(
            actuals=actuals,
            forecasts=forecasts,
            actual_quality=aq,
            forecast_quality=fq,
            provenance=provenance,
            fetched_at=fetched_at,
            notes=notes,
        )
