"""Request parameter validation and orchestration of one analysis run."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from . import analysis as an
from .config import Settings
from .models import Dataset
from .vintage import CutoffRule, DayAheadCutoff, HorizonCutoff, index_forecasts, select_for_targets

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
MAX_HORIZON_HOURS = 24 * 14


class ParamError(ValueError):
    """Invalid request parameter -> HTTP 422."""


@dataclass(frozen=True)
class Params:
    start: date
    end: date
    mode: str  # "day_ahead" | "horizon"
    cutoff_time: str
    lead_days: int
    horizon_hours: float | None


def _parse_date(name: str, value: str | None, default: date) -> date:
    if value is None or value == "":
        return default
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ParamError(f"{name} must be a date in YYYY-MM-DD format, got {value!r}") from exc


def parse_params(
    settings: Settings,
    start: str | None = None,
    end: str | None = None,
    mode: str | None = None,
    cutoff_time: str | None = None,
    lead_days: int | None = None,
    horizon_hours: float | None = None,
) -> Params:
    s = _parse_date("start", start, settings.period_start)
    e = _parse_date("end", end, settings.period_end)
    if s > e:
        raise ParamError("start must be on or before end")
    if s < settings.period_start or e > settings.period_end:
        raise ParamError(f"dates must lie within {settings.period_start} to {settings.period_end}")
    m = mode or "day_ahead"
    if m not in ("day_ahead", "horizon"):
        raise ParamError("mode must be 'day_ahead' or 'horizon'")
    ct = cutoff_time or settings.cutoff_time
    if not _HHMM.match(ct):
        raise ParamError("cutoff_time must be HH:MM (24-hour)")
    ld = settings.cutoff_lead_days if lead_days is None else lead_days
    if not 0 <= ld <= 7:
        raise ParamError("lead_days must be between 0 and 7")
    hh: float | None = None
    if m == "horizon":
        if horizon_hours is None:
            raise ParamError("horizon_hours is required when mode=horizon")
        if not 0 <= horizon_hours <= MAX_HORIZON_HOURS:
            raise ParamError(f"horizon_hours must be between 0 and {MAX_HORIZON_HOURS}")
        hh = float(horizon_hours)
    return Params(s, e, m, ct, ld, hh)


def make_rule(settings: Settings, p: Params) -> CutoffRule:
    if p.mode == "horizon":
        assert p.horizon_hours is not None
        return HorizonCutoff(p.horizon_hours)
    return DayAheadCutoff(settings.cutoff_timezone, p.cutoff_time, p.lead_days)


@dataclass
class Analysis:
    params: Params
    rule: CutoffRule
    lo: datetime
    hi: datetime
    rows: list[an.Row]
    metrics: dict
    daily: list[dict]
    tops: list[an.Row]
    quality: dict
    forecast_info: dict
    summary: list[str]


def run(dataset: Dataset, settings: Settings, p: Params) -> Analysis:
    lo, hi = an.local_day_window(p.start, p.end, settings.cutoff_timezone)
    targets = an.expected_intervals(lo, hi)
    rule = make_rule(settings, p)

    index = index_forecasts(dataset.forecasts)
    selections = select_for_targets(index, targets, rule)
    actuals_in_window = [a for a in dataset.actuals if lo <= a.start < hi]
    rows = an.build_rows(actuals_in_window, selections, targets)

    metrics = an.metrics_for_rows(rows)
    expected = len(rows)
    coverage = metrics["n"] / expected if expected else 0.0
    counts = {
        k: sum(1 for r in rows if r.status == k)
        for k in (an.MATCHED, an.MISSING_ACTUAL, an.MISSING_FORECAST, an.MISSING_BOTH)
    }
    forecasts_in_window = sum(len(v) for t, v in index.items() if lo <= t < hi)

    reasons: list[str] = []
    if dataset.provenance == "synthetic":
        reasons.append("Data are synthetic development fixtures, not Elexon data.")
    if metrics["n"] == 0:
        reasons.append("No matched forecast/actual pairs.")
    elif coverage < settings.min_authoritative_coverage:
        reasons.append(
            f"Coverage {coverage * 100:.1f}% is below the {settings.min_authoritative_coverage * 100:.0f}% threshold."
        )
    authoritative = not reasons

    used = [r.publish for r in rows if r.publish is not None]
    forecast_info = {
        "latest_publish_used": max(used) if used else None,
        "earliest_publish_used": min(used) if used else None,
        "distinct_publish_times_used": len(set(used)),
        "latest_publish_in_dataset": max((f.publish for f in dataset.forecasts), default=None),
    }
    quality = {
        "data_source": dataset.provenance,
        "fetched_at": dataset.fetched_at,
        "notes": dataset.notes,
        "actual_records_valid_in_period": len(actuals_in_window),
        "forecast_records_valid_in_period": forecasts_in_window,
        "actual_cleaning": dataset.actual_quality.as_dict(),
        "forecast_cleaning": dataset.forecast_quality.as_dict(),
        "expected_intervals": expected,
        "matched_intervals": counts[an.MATCHED],
        "missing_actual_only": counts[an.MISSING_ACTUAL],
        "missing_forecast_only": counts[an.MISSING_FORECAST],
        "missing_both": counts[an.MISSING_BOTH],
        "missing_intervals": expected - counts[an.MATCHED],
        "coverage": coverage,
        "forecast_vintages_excluded_after_cutoff": sum(r.n_excluded_after_cutoff for r in rows),
        "cutoff": {
            "mode": p.mode,
            "rule": rule.describe(),
            "first": rows[0].cutoff if rows else None,
            "last": rows[-1].cutoff if rows else None,
            "is_assumption": True,
        },
        "missing_runs": an.missing_runs(rows)[:50],
        "authoritative": authoritative,
        "not_authoritative_reasons": reasons,
    }
    daily = an.daily_summary(rows, settings.cutoff_timezone)
    tops = an.top_errors(rows, 10)
    return Analysis(
        p,
        rule,
        lo,
        hi,
        rows,
        metrics,
        daily,
        tops,
        quality,
        forecast_info,
        an.narrative(metrics, coverage, daily, tops, authoritative),
    )


def utc_iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
