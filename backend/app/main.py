"""FastAPI application: a small JSON API over the in-memory dataset.

FastAPI was chosen over Flask because request parameters get declared and documented
(/docs) with little code, and its test client + dependency overrides keep API tests simple.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import analysis as an
from .config import Settings, load_settings
from .elexon import ElexonError
from .service import Analysis, ParamError, parse_params, run, utc_iso
from .store import DataStore, DataUnavailable
from .vintage import index_forecasts

VERSION = "0.1.0"


def _iso(dt: datetime | None) -> str | None:
    return utc_iso(dt)


def _row(r: an.Row) -> dict[str, Any]:
    return {
        "t": _iso(r.start),
        "status": r.status,
        "actual_mw": r.actual,
        "forecast_mw": r.forecast,
        "error_mw": r.error,
        "abs_error_mw": r.abs_error,
        "publish_time": _iso(r.publish),
        "cutoff": _iso(r.cutoff),
        "vintages_eligible": r.n_eligible,
        "vintages_excluded_after_cutoff": r.n_excluded_after_cutoff,
    }


def _quality_json(q: dict[str, Any]) -> dict[str, Any]:
    out = dict(q)
    c = dict(q["cutoff"])
    c["first"], c["last"] = _iso(c["first"]), _iso(c["last"])
    out["cutoff"] = c
    out["missing_runs"] = [{**m, "from": _iso(m["from"]), "to": _iso(m["to"])} for m in q["missing_runs"]]
    return out


def _metrics_json(a: Analysis) -> dict[str, Any]:
    return {
        **a.metrics,
        "coverage": a.quality["coverage"],
        "expected_intervals": a.quality["expected_intervals"],
        "authoritative": a.quality["authoritative"],
        "not_authoritative_reasons": a.quality["not_authoritative_reasons"],
        "data_source": a.quality["data_source"],
        "definitions": {
            "error": "forecast - actual (MW); positive = over-forecast",
            "mae_mw": "mean(|error|)",
            "rmse_mw": "sqrt(mean(error^2))",
            "bias_mw": "mean(error)",
            "nmae_pct": "MAE / mean(actual) x 100, over the same matched pairs",
        },
    }


def create_app(settings: Settings | None = None, store: DataStore | None = None) -> FastAPI:
    settings = settings or load_settings()
    store = store or DataStore(settings)
    app = FastAPI(title="Wind Forecast Desk API", version=VERSION)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"], allow_headers=["*"]
    )

    @app.exception_handler(ParamError)
    async def _param_error(_, exc: ParamError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ElexonError)
    async def _elexon_error(_, exc: ElexonError):
        return JSONResponse(status_code=502, content={"detail": f"Upstream Elexon error: {exc}"})

    @app.exception_handler(DataUnavailable)
    async def _unavailable(_, exc: DataUnavailable):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    def analysis(
        start: str | None,
        end: str | None,
        mode: str | None,
        cutoff_time: str | None,
        lead_days: int | None,
        horizon_hours: float | None,
    ) -> Analysis:
        p = parse_params(settings, start, end, mode, cutoff_time, lead_days, horizon_hours)
        return run(store.get(), settings, p)

    # Shared query declarations
    Q_START = Query(None, description="YYYY-MM-DD (London local date), default period start")
    Q_END = Query(None, description="YYYY-MM-DD inclusive, default period end")
    Q_MODE = Query(None, description="day_ahead (default) or horizon")
    Q_CUT = Query(None, description="HH:MM London wall-clock cutoff (day_ahead mode)")
    Q_LEAD = Query(None, description="Days before delivery day for the cutoff (0-7)")
    Q_HOR = Query(None, description="Hours before each interval (horizon mode)")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": VERSION,
            "data_mode": settings.data_mode,
            "dataset_loaded": store.loaded_provenance() is not None,
            "data_source": store.loaded_provenance(),
        }

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        return {
            "period_start": settings.period_start.isoformat(),
            "period_end": settings.period_end.isoformat(),
            "timezone": settings.cutoff_timezone,
            "default_cutoff_time": settings.cutoff_time,
            "default_lead_days": settings.cutoff_lead_days,
            "min_authoritative_coverage": settings.min_authoritative_coverage,
            "cutoff_is_assumption": True,
        }

    @app.get("/api/series")
    def series(
        start: str | None = Q_START,
        end: str | None = Q_END,
        mode: str | None = Q_MODE,
        cutoff_time: str | None = Q_CUT,
        lead_days: int | None = Q_LEAD,
        horizon_hours: float | None = Q_HOR,
    ) -> dict[str, Any]:
        a = analysis(start, end, mode, cutoff_time, lead_days, horizon_hours)
        return {
            "data_source": a.quality["data_source"],
            "error_definition": "forecast - actual (MW)",
            "cutoff_rule": a.rule.describe(),
            "points": [_row(r) for r in a.rows],
        }

    @app.get("/api/metrics")
    def metrics(
        start: str | None = Q_START,
        end: str | None = Q_END,
        mode: str | None = Q_MODE,
        cutoff_time: str | None = Q_CUT,
        lead_days: int | None = Q_LEAD,
        horizon_hours: float | None = Q_HOR,
    ) -> dict[str, Any]:
        return _metrics_json(analysis(start, end, mode, cutoff_time, lead_days, horizon_hours))

    @app.get("/api/quality")
    def quality(
        start: str | None = Q_START,
        end: str | None = Q_END,
        mode: str | None = Q_MODE,
        cutoff_time: str | None = Q_CUT,
        lead_days: int | None = Q_LEAD,
        horizon_hours: float | None = Q_HOR,
    ) -> dict[str, Any]:
        return _quality_json(analysis(start, end, mode, cutoff_time, lead_days, horizon_hours).quality)

    @app.get("/api/summary")
    def summary(
        start: str | None = Q_START,
        end: str | None = Q_END,
        mode: str | None = Q_MODE,
        cutoff_time: str | None = Q_CUT,
        lead_days: int | None = Q_LEAD,
        horizon_hours: float | None = Q_HOR,
    ) -> dict[str, Any]:
        """Everything the dashboard needs in one call."""
        a = analysis(start, end, mode, cutoff_time, lead_days, horizon_hours)
        return {
            "period": {"start": a.params.start.isoformat(), "end": a.params.end.isoformat()},
            "metrics": _metrics_json(a),
            "quality": _quality_json(a.quality),
            "forecast_info": {
                k: _iso(v) if isinstance(v, datetime) else v for k, v in a.forecast_info.items()
            },
            "daily": a.daily,
            "top_errors": [_row(r) for r in a.tops],
            "summary": a.summary,
        }

    @app.get("/api/actuals")
    def actuals(start: str | None = Q_START, end: str | None = Q_END) -> dict[str, Any]:
        p = parse_params(settings, start, end)
        ds = store.get()
        lo, hi = an.local_day_window(p.start, p.end, settings.cutoff_timezone)
        pts = [{"t": _iso(x.start), "actual_mw": x.mw} for x in ds.actuals if lo <= x.start < hi]
        return {"data_source": ds.provenance, "count": len(pts), "points": pts}

    @app.get("/api/forecasts")
    def forecasts(
        start: str | None = Q_START,
        end: str | None = Q_END,
        limit: int = Query(2000, ge=1, le=20000),
    ) -> dict[str, Any]:
        """All forecast vintages (unselected) for the window, capped by `limit`."""
        p = parse_params(settings, start, end)
        ds = store.get()
        lo, hi = an.local_day_window(p.start, p.end, settings.cutoff_timezone)
        rows = [f for f in ds.forecasts if lo <= f.start < hi]
        return {
            "data_source": ds.provenance,
            "count": len(rows),
            "truncated": len(rows) > limit,
            "points": [
                {"t": _iso(f.start), "publish_time": _iso(f.publish), "forecast_mw": f.mw}
                for f in rows[:limit]
            ],
        }

    @app.get("/api/vintages")
    def vintages(
        target: str = Query(..., description="Delivery interval start, ISO-8601 UTC"),
        mode: str | None = Q_MODE,
        cutoff_time: str | None = Q_CUT,
        lead_days: int | None = Q_LEAD,
        horizon_hours: float | None = Q_HOR,
    ) -> dict[str, Any]:
        """Every published forecast for one interval, flagged eligible/selected at the cutoff."""
        from .cleaning import parse_ts
        from .service import make_rule
        from .vintage import select_vintage

        t = parse_ts(target)
        if t is None or t.minute not in (0, 30) or t.second:
            raise ParamError("target must be an ISO-8601 timestamp on a half-hour boundary")
        p = parse_params(settings, None, None, mode, cutoff_time, lead_days, horizon_hours)
        ds = store.get()
        rule = make_rule(settings, p)
        cutoff = rule.cutoff_for(t)
        vs = index_forecasts(ds.forecasts).get(t, [])
        chosen = select_vintage(vs, cutoff)
        actual = next((x.mw for x in ds.actuals if x.start == t), None)
        return {
            "data_source": ds.provenance,
            "target": _iso(t),
            "cutoff": _iso(cutoff),
            "cutoff_rule": rule.describe(),
            "actual_mw": actual,
            "vintages": [
                {
                    "publish_time": _iso(v.publish),
                    "forecast_mw": v.mw,
                    "hours_before_delivery": (t - v.publish).total_seconds() / 3600,
                    "eligible": v.publish <= cutoff,
                    "selected": chosen is not None and v is chosen,
                    "error_mw": None if actual is None else v.mw - actual,
                }
                for v in vs
            ],
        }

    # Optional: serve the built frontend from the same origin (single-container deployment).
    static_dir = settings.static_dir
    if static_dir and static_dir.is_dir():
        index = static_dir / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            candidate = (static_dir / full_path).resolve()
            if full_path and candidate.is_file() and static_dir.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(index)

    return app


app = create_app()  # the dataset is loaded lazily on first data request, not at import
