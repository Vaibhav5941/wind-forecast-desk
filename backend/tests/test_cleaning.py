from app.cleaning import clean_actuals, clean_forecasts, parse_generation, parse_ts

from .helpers import utc


def a(start="2026-01-10T12:00:00Z", gen=100, fuel="WIND", pub=None):
    r = {"startTime": start, "generation": gen, "fuelType": fuel}
    if pub:
        r["publishTime"] = pub
    return r


def f(start="2026-01-10T12:00:00Z", pub="2026-01-09T06:00:00Z", gen=100):
    return {"startTime": start, "publishTime": pub, "generation": gen}


def test_only_wind_actuals_are_kept():
    out, q = clean_actuals([a(fuel="WIND"), a(fuel="CCGT", start="2026-01-10T12:30:00Z")])
    assert len(out) == 1 and q.ignored_other_fuel == 1


def test_null_generation_is_excluded_not_zero_filled():
    out, q = clean_actuals([a(gen=None)])
    assert out == [] and q.null_generation == 1


def test_invalid_generation_values_are_excluded_and_counted():
    out, q = clean_actuals(
        [
            a(gen=-5),
            a(gen="abc", start="2026-01-10T12:30:00Z"),
            a(gen=float("nan"), start="2026-01-10T13:00:00Z"),
            a(gen=1e9, start="2026-01-10T13:30:00Z"),
        ]
    )
    assert out == [] and q.invalid_generation == 4


def test_zero_is_a_valid_generation_value():
    out, _ = clean_actuals([a(gen=0)])
    assert out[0].mw == 0


def test_bool_is_not_a_number():
    assert parse_generation(True) == (None, "invalid")


def test_exact_duplicate_actuals_are_collapsed_and_counted():
    out, q = clean_actuals([a(), a()])
    assert len(out) == 1 and q.duplicate_records == 1 and q.conflicting_duplicates == 0


def test_conflicting_duplicates_are_flagged_and_latest_published_wins():
    out, q = clean_actuals(
        [
            a(gen=100, pub="2026-01-10T12:30:00Z"),
            a(gen=150, pub="2026-01-10T13:30:00Z"),
            a(gen=90, pub="2026-01-10T12:00:00Z"),  # older publish arrives last, must not win
        ]
    )
    assert len(out) == 1 and out[0].mw == 150
    assert q.duplicate_records == 2 and q.conflicting_duplicates == 2


def test_misaligned_and_unparseable_timestamps_are_rejected():
    out, q = clean_actuals([a(start="2026-01-10T12:17:00Z"), a(start="not a date"), a(start=None)])
    assert out == [] and q.invalid_timestamp == 3


def test_offset_timestamps_are_normalised_to_utc():
    assert parse_ts("2026-07-01T00:30:00+01:00") == utc(30, 23, 30, month=6)


def test_naive_timestamps_are_treated_as_utc_and_counted():
    out, q = clean_actuals([a(start="2026-01-10T12:00:00")])
    assert out[0].start == utc(10, 12) and q.naive_timestamps == 1


def test_forecast_duplicates_keyed_on_interval_and_publish_time():
    out, q = clean_forecasts([f(), f(), f(pub="2026-01-09T09:00:00Z", gen=200)])
    assert len(out) == 2 and q.duplicate_records == 1


def test_forecast_missing_publish_time_is_invalid():
    out, q = clean_forecasts([{"startTime": "2026-01-10T12:00:00Z", "generation": 5}])
    assert out == [] and q.invalid_timestamp == 1


def test_forecast_null_generation_excluded():
    out, q = clean_forecasts([f(gen=None)])
    assert out == [] and q.null_generation == 1


def test_empty_input():
    assert clean_actuals([])[0] == [] and clean_forecasts([])[0] == []
