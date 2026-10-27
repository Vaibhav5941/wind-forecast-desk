from datetime import timedelta

from app.vintage import (
    DayAheadCutoff,
    HorizonCutoff,
    index_forecasts,
    select_for_targets,
    select_vintage,
)

from .helpers import fc, utc


def test_selects_latest_vintage_published_at_or_before_cutoff():
    t = utc(10, 12)
    cutoff = utc(9, 9)  # day before, 09:00 (London == UTC in January)
    vs = [
        fc(t, utc(8, 6), 100),
        fc(t, utc(9, 3), 200),
        fc(t, utc(9, 8, 30), 300),  # latest before cutoff -> expected
        fc(t, utc(9, 10), 400),  # after cutoff
    ]
    assert select_vintage(vs, cutoff).mw == 300


def test_forecast_published_after_cutoff_is_excluded_even_if_it_is_the_only_one():
    t = utc(10, 12)
    vs = [fc(t, utc(9, 9, 1), 999)]  # one minute late
    assert select_vintage(vs, utc(9, 9)) is None


def test_cutoff_is_inclusive():
    t = utc(10, 12)
    vs = [fc(t, utc(9, 9), 123)]
    assert select_vintage(vs, utc(9, 9)).mw == 123


def test_day_ahead_cutoff_is_previous_day_at_clock_time_london():
    rule = DayAheadCutoff(tz="Europe/London", clock="09:00", lead_days=1)
    # every interval of 10 Jan shares the 9 Jan 09:00 cutoff (UTC == London in January)
    assert rule.cutoff_for(utc(10, 0, 0)) == utc(9, 9)
    assert rule.cutoff_for(utc(10, 23, 30)) == utc(9, 9)


def test_day_ahead_cutoff_uses_london_local_date_in_summer():
    # 23:30 UTC on 30 Jun is 00:30 BST on 1 Jul -> delivery day is 1 Jul, cutoff 30 Jun 09:00 BST = 08:00 UTC
    rule = DayAheadCutoff(tz="Europe/London", clock="09:00", lead_days=1)
    t = utc(30, 23, 30, month=6)
    assert rule.cutoff_for(t) == utc(30, 8, 0, month=6)


def test_day_ahead_cutoff_is_configurable():
    rule = DayAheadCutoff(clock="11:00", lead_days=2)
    assert rule.cutoff_for(utc(10, 12)) == utc(8, 11)


def test_horizon_cutoff():
    assert HorizonCutoff(24).cutoff_for(utc(10, 12)) == utc(9, 12)


def test_select_for_targets_counts_excluded_and_eligible():
    t = utc(10, 12)
    idx = index_forecasts(
        [fc(t, utc(8, 12), 1), fc(t, utc(9, 8), 2), fc(t, utc(9, 12), 3), fc(t, utc(10, 6), 4)]
    )
    sel = select_for_targets(idx, [t], DayAheadCutoff())[t]
    assert sel.forecast.mw == 2
    assert sel.n_eligible == 2
    assert sel.n_excluded_after_cutoff == 2


def test_no_eligible_forecast_gives_none_not_zero():
    t = utc(10, 12)
    idx = index_forecasts([fc(t, utc(9, 15), 5)])
    sel = select_for_targets(idx, [t], DayAheadCutoff())[t]
    assert sel.forecast is None


def test_earlier_vintage_can_be_inspected_with_horizon_rule():
    t = utc(10, 12)
    idx = index_forecasts([fc(t, t - timedelta(hours=48), 10), fc(t, t - timedelta(hours=6), 20)])
    assert select_for_targets(idx, [t], HorizonCutoff(36))[t].forecast.mw == 10
    assert select_for_targets(idx, [t], HorizonCutoff(3))[t].forecast.mw == 20
