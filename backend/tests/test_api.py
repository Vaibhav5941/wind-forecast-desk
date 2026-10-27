import gzip
import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.elexon import ElexonClient, ElexonError
from app.main import create_app
from app.service import ParamError, parse_params
from app.store import DataStore, DataUnavailable


def synthetic_client(tmp_path: Path) -> TestClient:
    s = Settings(data_mode="synthetic", snapshot_dir=tmp_path)
    return TestClient(create_app(s, DataStore(s)))


def test_health_ok(tmp_path):
    r = synthetic_client(tmp_path).get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_summary_shape_and_synthetic_labelling(tmp_path):
    j = synthetic_client(tmp_path).get("/api/summary?start=2026-01-05&end=2026-01-07").json()
    assert j["quality"]["data_source"] == "synthetic"
    assert j["metrics"]["authoritative"] is False
    assert j["metrics"]["definitions"]["error"].startswith("forecast - actual")
    assert j["quality"]["cutoff"]["is_assumption"] is True
    assert len(j["daily"]) == 3 and j["metrics"]["n"] > 0


def test_series_has_no_forecast_published_after_cutoff(tmp_path):
    pts = synthetic_client(tmp_path).get("/api/series?start=2026-01-05&end=2026-01-06").json()["points"]
    used = [p for p in pts if p["publish_time"]]
    assert used and all(p["publish_time"] <= p["cutoff"] for p in used)
    assert any(p["vintages_excluded_after_cutoff"] > 0 for p in pts)


def test_series_error_is_forecast_minus_actual(tmp_path):
    for p in synthetic_client(tmp_path).get("/api/series?start=2026-01-05&end=2026-01-05").json()["points"]:
        if p["status"] == "matched":
            assert p["error_mw"] == pytest.approx(p["forecast_mw"] - p["actual_mw"])
            assert p["abs_error_mw"] == abs(p["error_mw"])


def test_horizon_mode_and_vintage_endpoint(tmp_path):
    c = synthetic_client(tmp_path)
    assert (
        c.get("/api/metrics?mode=horizon&horizon_hours=6&start=2026-01-05&end=2026-01-05").status_code == 200
    )
    v = c.get("/api/vintages?target=2026-01-05T12:00:00Z").json()
    assert sum(1 for x in v["vintages"] if x["selected"]) == 1
    assert all(x["eligible"] for x in v["vintages"] if x["selected"])
    late = [x for x in v["vintages"] if x["publish_time"] > v["cutoff"]]
    assert late and not any(x["eligible"] or x["selected"] for x in late)


@pytest.mark.parametrize(
    "qs",
    [
        "start=2025-12-31",
        "end=2026-02-01",
        "start=2026-01-10&end=2026-01-05",
        "start=banana",
        "mode=weird",
        "cutoff_time=25:00",
        "lead_days=99",
        "mode=horizon",
        "mode=horizon&horizon_hours=-1",
        "mode=horizon&horizon_hours=99999",
    ],
)
def test_invalid_parameters_return_422(tmp_path, qs):
    r = synthetic_client(tmp_path).get(f"/api/metrics?{qs}")
    assert r.status_code == 422, qs


def test_invalid_vintage_target_422(tmp_path):
    assert synthetic_client(tmp_path).get("/api/vintages?target=2026-01-05T12:07:00Z").status_code == 422


def test_parse_params_defaults():
    p = parse_params(Settings())
    assert p.start == date(2026, 1, 1) and p.end == date(2026, 1, 31) and p.mode == "day_ahead"


def test_empty_dataset_endpoint_returns_nulls(tmp_path):
    s = Settings(data_mode="synthetic", snapshot_dir=tmp_path)
    store = DataStore(s)
    from app.models import Dataset

    store._dataset = Dataset(provenance="cached")
    j = TestClient(create_app(s, store)).get("/api/summary").json()
    assert j["metrics"]["n"] == 0 and j["metrics"]["mae_mw"] is None
    assert j["quality"]["coverage"] == 0 and j["quality"]["authoritative"] is False


# ---- upstream behaviour ---------------------------------------------------------------


def mock_client(handler, retries=3) -> ElexonClient:
    s = Settings(elexon_retries=retries)
    return ElexonClient(s, httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None)


def test_upstream_5xx_is_retried_then_succeeds():
    calls = []

    def h(req):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json=[{"a": 1}])

    out = mock_client(h)._get_json("/x", {})
    assert out == [{"a": 1}] and len(calls) == 3


def test_upstream_persistent_5xx_raises_elexon_error():
    with pytest.raises(ElexonError):
        mock_client(lambda r: httpx.Response(500))._get_json("/x", {})


def test_upstream_4xx_is_not_retried():
    calls = []

    def h(req):
        calls.append(1)
        return httpx.Response(400, text="bad")

    with pytest.raises(ElexonError):
        mock_client(h)._get_json("/x", {})
    assert len(calls) == 1


def test_upstream_network_error_and_bad_json():
    def boom(req):
        raise httpx.ConnectError("down")

    with pytest.raises(ElexonError):
        mock_client(boom, retries=2)._get_json("/x", {})
    with pytest.raises(ElexonError):
        mock_client(lambda r: httpx.Response(200, text="<html>"))._get_json("/x", {})
    with pytest.raises(ElexonError):
        mock_client(lambda r: httpx.Response(200, json={"oops": 1}))._get_json("/x", {})


def test_stream_chunks_requests_and_passes_fuel_type():
    seen = []

    def h(req):
        seen.append(dict(req.url.params))
        return httpx.Response(200, json=[])

    from tests.helpers import utc

    mock_client(h).fetch_wind_actuals(utc(1), utc(8))
    assert len(seen) == 3 and all(p["fuelType"] == "WIND" for p in seen)


def test_auto_mode_falls_back_to_labelled_synthetic_when_upstream_down(tmp_path):
    s = Settings(data_mode="auto", snapshot_dir=tmp_path, allow_synthetic_fallback=True)
    store = DataStore(s, lambda: mock_client(lambda r: httpx.Response(503), retries=1))
    ds = store.get()
    assert ds.provenance == "synthetic" and "SYNTHETIC" in ds.notes[0]
    assert not store.snapshot_path.exists()  # synthetic data is never snapshotted


def test_fallback_disabled_gives_503_from_api(tmp_path):
    s = Settings(data_mode="auto", snapshot_dir=tmp_path, allow_synthetic_fallback=False)
    store = DataStore(s, lambda: mock_client(lambda r: httpx.Response(503), retries=1))
    r = TestClient(create_app(s, store)).get("/api/summary")
    assert r.status_code == 503


def test_live_fetch_writes_snapshot_then_serves_it_as_cached(tmp_path):
    def h(req):
        if "FUELHH" in req.url.path:
            return httpx.Response(
                200, json=[{"startTime": "2026-01-05T12:00:00Z", "fuelType": "WIND", "generation": 5000}]
            )
        return httpx.Response(
            200,
            json=[
                {
                    "startTime": "2026-01-05T12:00:00Z",
                    "publishTime": "2026-01-04T06:00:00Z",
                    "generation": 5100,
                }
            ],
        )

    s = Settings(data_mode="live", snapshot_dir=tmp_path)
    ds = DataStore(s, lambda: mock_client(h)).get()
    assert ds.provenance == "live"
    s2 = Settings(data_mode="snapshot", snapshot_dir=tmp_path)
    ds2 = DataStore(s2).get()
    assert ds2.provenance == "cached" and len(ds2.actuals) == 1


def test_snapshot_mode_without_snapshot_raises(tmp_path):
    with pytest.raises(DataUnavailable):
        DataStore(Settings(data_mode="snapshot", snapshot_dir=tmp_path)).get()


def test_synthetic_snapshot_is_refused(tmp_path):
    s = Settings(data_mode="snapshot", snapshot_dir=tmp_path)
    store = DataStore(s)
    with gzip.open(store.snapshot_path, "wt") as fh:
        json.dump({"meta": {"synthetic": True}, "actuals_raw": [], "forecasts_raw": []}, fh)
    with pytest.raises(DataUnavailable):
        store.get()


def test_param_error_type():
    with pytest.raises(ParamError):
        parse_params(Settings(), start="nope")
