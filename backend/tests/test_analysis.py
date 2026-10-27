import math
from datetime import date

from app import analysis as an
from app.config import Settings
from app.models import Dataset
from app.service import Params, run
from app.vintage import DayAheadCutoff, index_forecasts, select_for_targets

from .helpers import act, fc, half_hours, utc

RULE = DayAheadCutoff()


def rows_for(actuals, forecasts, targets):
    sel = select_for_targets(index_forecasts(forecasts), targets, RULE)
    return an.build_rows(actuals, sel, targets)


def test_matching_joins_on_delivery_interval_not_on_position():
    ts = half_hours(utc(10), 3)
    # forecast list deliberately in a different order and with a gap in the actuals
    forecasts = [fc(ts[2], utc(9, 6), 300), fc(ts[0], utc(9, 6), 100), fc(ts[1], utc(9, 6), 200)]
    actuals = [act(ts[2], 310), act(ts[0], 90)]
    rows = rows_for(actuals, forecasts, ts)
    assert [r.status for r in rows] == [an.MATCHED, an.MISSING_ACTUAL, an.MATCHED]
    assert rows[0].error == 10 and rows[2].error == -10


def test_bias_sign_forecast_minus_actual():
    ts = half_hours(utc(10), 2)
    over = rows_for([act(ts[0], 100)], [fc(ts[0], utc(9, 6), 150)], ts[:1])[0]
    under = rows_for([act(ts[1], 100)], [fc(ts[1], utc(9, 6), 60)], ts[1:])[0]
    assert over.error == 50  # over-forecast is positive
    assert under.error == -40  # under-forecast is negative
    assert under.abs_error == 40


def test_metrics_known_values():
    # errors: +10, -30, +20 -> MAE 20, RMSE sqrt((100+900+400)/3), bias 0
    m = an.compute_metrics([10, -30, 20], [100, 100, 100])
    assert m["n"] == 3
    assert m["mae_mw"] == 20
    assert math.isclose(m["rmse_mw"], math.sqrt(1400 / 3))
    assert m["bias_mw"] == 0
    assert math.isclose(m["nmae_pct"], 20.0)


def test_metrics_use_only_valid_matched_pairs():
    ts = half_hours(utc(10), 4)
    forecasts = [fc(ts[0], utc(9, 6), 110), fc(ts[1], utc(9, 6), 500), fc(ts[2], utc(9, 6), 200)]
    actuals = [act(ts[0], 100), act(ts[2], 180), act(ts[3], 777)]  # ts[1] no actual, ts[3] no forecast
    m = an.metrics_for_rows(rows_for(actuals, forecasts, ts))
    assert m["n"] == 2
    assert m["mae_mw"] == 15  # (10 + 20) / 2; the unmatched 500 and 777 play no part
    assert m["bias_mw"] == 15


def test_late_forecast_never_enters_metrics():
    ts = half_hours(utc(10), 1)
    forecasts = [fc(ts[0], utc(9, 6), 100), fc(ts[0], utc(9, 20), 9999)]
    m = an.metrics_for_rows(rows_for([act(ts[0], 100)], forecasts, ts))
    assert m["mae_mw"] == 0


def test_missing_values_are_never_zero_filled():
    ts = half_hours(utc(10), 2)
    rows = rows_for([], [fc(ts[0], utc(9, 6), 100)], ts)
    assert rows[0].status == an.MISSING_ACTUAL and rows[0].actual is None
    assert rows[1].status == an.MISSING_BOTH and rows[1].forecast is None
    assert an.metrics_for_rows(rows)["n"] == 0


def test_empty_dataset_gives_null_metrics_not_errors():
    m = an.compute_metrics([], [])
    assert m["n"] == 0 and m["mae_mw"] is None and m["rmse_mw"] is None and m["bias_mw"] is None


def test_nmae_undefined_when_mean_actual_is_zero():
    assert an.compute_metrics([5, -5], [0, 0])["nmae_pct"] is None


def test_missing_runs_group_contiguous_gaps():
    ts = half_hours(utc(10), 6)
    forecasts = [fc(t, utc(9, 6), 1) for t in ts]
    actuals = [act(ts[0], 1), act(ts[4], 1), act(ts[5], 1)]  # gap at ts[1..3]
    runs = an.missing_runs(rows_for(actuals, forecasts, ts))
    assert len(runs) == 1 and runs[0]["intervals"] == 3 and runs[0]["from"] == ts[1]


def test_daily_summary_groups_by_london_day():
    ts = half_hours(utc(10), 96)  # two full days
    forecasts = [fc(t, utc(8, 6), 110) for t in ts]
    actuals = [act(t, 100) for t in ts]
    daily = an.daily_summary(rows_for(actuals, forecasts, ts))
    assert [d["date"] for d in daily] == ["2026-01-10", "2026-01-11"]
    assert daily[0]["expected_intervals"] == 48 and daily[0]["bias_mw"] == 10


def test_dst_days_have_46_and_50_intervals():
    lo, hi = an.local_day_window(date(2026, 3, 29), date(2026, 3, 29))  # clocks go forward
    assert len(an.expected_intervals(lo, hi)) == 46
    lo, hi = an.local_day_window(date(2026, 10, 25), date(2026, 10, 25))  # clocks go back
    assert len(an.expected_intervals(lo, hi)) == 50


def test_run_flags_synthetic_and_low_coverage_as_not_authoritative():
    s = Settings()
    ts = half_hours(utc(1), 48)
    ds = Dataset(
        actuals=[act(t, 100) for t in ts[:24]],
        forecasts=[fc(t, utc(1) - __import__("datetime").timedelta(days=1, hours=3), 110) for t in ts],
        provenance="synthetic",
    )
    out = run(ds, s, Params(date(2026, 1, 1), date(2026, 1, 1), "day_ahead", "09:00", 1, None))
    assert out.quality["authoritative"] is False
    assert out.quality["matched_intervals"] == 24 and out.quality["missing_intervals"] == 24
    assert out.quality["missing_actual_only"] == 24
    assert any("synthetic" in r.lower() for r in out.quality["not_authoritative_reasons"])
    assert any("coverage" in r.lower() for r in out.quality["not_authoritative_reasons"])


def test_run_authoritative_only_for_real_provenance_with_full_coverage():
    s = Settings()
    ts = half_hours(utc(1), 48)
    from datetime import timedelta

    ds = Dataset(
        actuals=[act(t, 100) for t in ts],
        forecasts=[fc(t, utc(1) - timedelta(days=1, hours=3), 110) for t in ts],
        provenance="cached",
    )
    out = run(ds, s, Params(date(2026, 1, 1), date(2026, 1, 1), "day_ahead", "09:00", 1, None))
    assert out.quality["authoritative"] is True and out.metrics["bias_mw"] == 10
