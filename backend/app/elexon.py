"""Thin client for the Elexon Insights (BMRS) dataset stream endpoints.

NOTE - UNVERIFIED API DETAILS. The build environment could not reach bmrs.elexon.co.uk, so
the base URL, query parameter names and response shape below follow the Insights API as
the author understands it, and have NOT been confirmed against live responses. Parameter
names are configurable (see config.py). First live run should be checked - see README.

Assumed shape of a stream response: a JSON array of objects, e.g.
  FUELHH : {dataset, publishTime, startTime, settlementDate, settlementPeriod, fuelType, generation}
  WINDFOR: {dataset, publishTime, startTime, generation}
`generation` is assumed to be MW (average over the half-hour for FUELHH).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from .config import Settings


class ElexonError(Exception):
    """Upstream (Elexon) failure that the caller should surface as a 502/503."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ElexonClient:
    def __init__(
        self,
        settings: Settings,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.s = settings
        self._http = http or httpx.Client(timeout=settings.elexon_timeout_s)
        self._sleep = sleep

    def _get_json(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self.s.elexon_base_url}{path}"
        last: Exception | None = None
        for attempt in range(max(1, self.s.elexon_retries)):
            try:
                resp = self._http.get(url, params=params, headers={"Accept": "application/json"})
            except httpx.HTTPError as exc:  # timeouts, connection errors
                last = ElexonError(f"Could not reach Elexon: {exc.__class__.__name__}: {exc}")
            else:
                if resp.status_code == 200:
                    try:
                        body = resp.json()
                    except ValueError as exc:
                        raise ElexonError("Elexon returned a non-JSON response") from exc
                    if isinstance(body, dict) and isinstance(body.get("data"), list):
                        body = body["data"]
                    if not isinstance(body, list):
                        raise ElexonError("Unexpected Elexon response shape (expected a JSON array)")
                    return body
                if resp.status_code in (429, 500, 502, 503, 504):
                    last = ElexonError(
                        f"Elexon temporarily unavailable (HTTP {resp.status_code})", resp.status_code
                    )
                else:
                    # 4xx other than 429: retrying will not help (bad parameters, etc.)
                    raise ElexonError(
                        f"Elexon rejected the request (HTTP {resp.status_code}): {resp.text[:200]}",
                        resp.status_code,
                    )
            if attempt < self.s.elexon_retries - 1:
                self._sleep(min(2**attempt, 8))
        assert last is not None
        raise last

    def _stream(
        self, dataset: str, lo: datetime, hi: datetime, extra: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        step = timedelta(days=max(1, self.s.elexon_chunk_days))
        t = lo
        while t < hi:
            nxt = min(t + step, hi)
            params = {self.s.elexon_from_param: _iso(t), self.s.elexon_to_param: _iso(nxt)}
            params.update(extra or {})
            out.extend(self._get_json(f"/datasets/{dataset}/stream", params))
            t = nxt
        return out

    def fetch_wind_actuals(self, lo: datetime, hi: datetime) -> list[dict[str, Any]]:
        return self._stream("FUELHH", lo, hi, {"fuelType": "WIND"})

    def fetch_wind_forecasts(self, lo: datetime, hi: datetime) -> list[dict[str, Any]]:
        return self._stream("WINDFOR", lo, hi)
