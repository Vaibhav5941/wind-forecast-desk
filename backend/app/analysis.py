"""Matching forecast/actual pairs, error metrics and period summaries.

Sign convention (used everywhere, including the UI):
    error = forecast - actual
A positive error means the forecast OVER-predicted wind (the buyer would have bought too
little other power); a negative error means it UNDER-predicted wind (bought too much).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .models import INTERVAL_MINUTES, Actual
from .vintage import Selection

STEP = timedelta(minutes=INTERVAL_MINUTES)

# Row status values
MATCHED = "matched"
MISSING_ACTUAL = "missing_actual"
MISSING_FORECAST = "missing_forecast"  # no eligible vintage published by cutoff
MISSING_BOTH = "missing_both"


def local_day_window(start: date, end: date, tz: str = "Europe/London") -> tuple[datetime, datetime]:
    """UTC [start, end) covering whole local days start..end inclusive."""
    zone = ZoneInfo(tz)
    lo = datetime.combine(start, time(0, 0), tzinfo=zone).astimezone(UTC)
    hi = datetime.combine(end + timedelta(days=1), time(0, 0), tzinfo=zone).astimezone(UTC)
    return lo, hi


def expected_intervals(lo: datetime, hi: datetime) -> list[datetime]:
    out, t = [], lo
    while t < hi:
        out.append(t)
        t += STEP
    return out


@dataclass
class Row:
    start: datetime
    status: str
    actual: float | None
    forecast: float | None
    publish: datetime | None
    cutoff: datetime
    n_eligible: int
    n_excluded_after_cutoff: int

    @property
    def error(self) -> float | None:
        if self.status != MATCHED:
            return None
        assert self.forecast is not None and self.actual is not None
        return self.forecast - self.actual  # forecast MINUS actual

    @property
    def abs_error(self) -> float | None:
        e = self.error
        return None if e is None else abs(e)


def build_rows(
    actuals: list[Actual],
    selections: dict[datetime, Selection],
    targets: list[datetime],
) -> list[Row]:
    """Join on delivery interval start. Missing sides stay missing - never zero-filled."""
    actual_by_start = {a.start: a.mw for a in actuals}
    rows: list[Row] = []
    for t in targets:
        sel = selections[t]
        act = actual_by_start.get(t)
        fc = sel.forecast
        if act is not None and fc is not None:
            status = MATCHED
        elif act is None and fc is None:
            status = MISSING_BOTH
        elif act is None:
            status = MISSING_ACTUAL
        else:
            status = MISSING_FORECAST
        rows.append(
            Row(
                start=t,
                status=status,
                actual=act,
                forecast=None if fc is None else fc.mw,
                publish=None if fc is None else fc.publish,
                cutoff=sel.cutoff,
                n_eligible=sel.n_eligible,
                n_excluded_after_cutoff=sel.n_excluded_after_cutoff,
            )
        )
    return rows


def compute_metrics(errors: list[float], actuals: list[float]) -> dict[str, float | int | None]:
    """errors = forecast - actual for valid matched pairs only."""
    n = len(errors)
    if n == 0:
        return {
            "n": 0,
            "mae_mw": None,
            "rmse_mw": None,
            "bias_mw": None,
            "mean_actual_mw": None,
            "nmae_pct": None,
        }
    mae = sum(abs(e) for e in errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    bias = sum(errors) / n
    mean_actual = sum(actuals) / n
    # nMAE = MAE / mean actual output over the same pairs. Undefined when mean actual is 0.
    nmae = (mae / mean_actual * 100.0) if mean_actual > 0 else None
    return {
        "n": n,
        "mae_mw": mae,
        "rmse_mw": rmse,
        "bias_mw": bias,
        "mean_actual_mw": mean_actual,
        "nmae_pct": nmae,
    }


def metrics_for_rows(rows: list[Row]) -> dict[str, float | int | None]:
    matched = [r for r in rows if r.status == MATCHED]
    return compute_metrics(
        [r.error for r in matched],  # type: ignore[misc]
        [r.actual for r in matched],  # type: ignore[misc]
    )


def daily_summary(rows: list[Row], tz: str = "Europe/London") -> list[dict]:
    zone = ZoneInfo(tz)
    by_day: dict[date, list[Row]] = defaultdict(list)
    for r in rows:
        by_day[r.start.astimezone(zone).date()].append(r)
    out = []
    for day in sorted(by_day):
        day_rows = by_day[day]
        m = metrics_for_rows(day_rows)
        out.append(
            {
                "date": day.isoformat(),
                "expected_intervals": len(day_rows),
                "matched_intervals": m["n"],
                "coverage": m["n"] / len(day_rows) if day_rows else 0.0,
                **{k: v for k, v in m.items() if k != "n"},
            }
        )
    return out


def top_errors(rows: list[Row], n: int = 10) -> list[Row]:
    matched = [r for r in rows if r.status == MATCHED]
    return sorted(matched, key=lambda r: r.abs_error, reverse=True)[:n]  # type: ignore[arg-type,return-value]


def missing_runs(rows: list[Row]) -> list[dict]:
    """Contiguous runs of unmatched intervals, so gaps are visible as ranges not noise."""
    runs: list[dict] = []
    cur: list[Row] = []

    def flush() -> None:
        if cur:
            statuses = sorted({r.status for r in cur})
            runs.append(
                {
                    "from": cur[0].start,
                    "to": cur[-1].start + STEP,
                    "intervals": len(cur),
                    "statuses": statuses,
                }
            )

    for r in rows:
        if r.status != MATCHED:
            cur.append(r)
        else:
            flush()
            cur = []
    flush()
    return runs


def narrative(
    metrics: dict, coverage: float, daily: list[dict], tops: list[Row], authoritative: bool
) -> list[str]:
    """Short, strictly data-derived sentences. No claims beyond what the numbers show."""
    if not metrics["n"]:
        return [
            "No matched forecast/actual intervals in the selected period, so no accuracy figures are available."
        ]
    out = [
        f"Across {metrics['n']} matched half-hour intervals ({coverage * 100:.1f}% of the period), "
        f"the decision-time forecast had a mean absolute error of {metrics['mae_mw']:.0f} MW "
        f"(RMSE {metrics['rmse_mw']:.0f} MW)."
    ]
    bias = metrics["bias_mw"]
    if metrics["mae_mw"] and abs(bias) < 0.1 * metrics["mae_mw"]:
        verdict = "small relative to the typical error, so there is no clear systematic tilt"
    elif bias > 0:
        verdict = "on average the forecast over-predicted wind"
    else:
        verdict = "on average the forecast under-predicted wind"
    out.append(f"Mean bias was {bias:+.0f} MW (forecast minus actual): {verdict}.")
    scored = [d for d in daily if d["mae_mw"] is not None]
    if scored:
        worst = max(scored, key=lambda d: d["mae_mw"])
        best = min(scored, key=lambda d: d["mae_mw"])
        out.append(
            f"Daily MAE ranged from {best['mae_mw']:.0f} MW ({best['date']}) "
            f"to {worst['mae_mw']:.0f} MW ({worst['date']})."
        )
    if tops:
        t = tops[0]
        out.append(
            f"The largest single-interval miss was {t.error:+.0f} MW at "
            f"{t.start.strftime('%Y-%m-%d %H:%M')} UTC."
        )
    if not authoritative:
        out.append(
            "These figures are NOT authoritative: see the data-quality panel (coverage or data source)."
        )
    return out
