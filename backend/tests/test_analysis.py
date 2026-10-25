import math
import sqlite3
from datetime import date, datetime, time, timedelta, timezone

import pytest

from backend.app.analysis import (
    analyze_day,
    analyze_month,
    calculate_metrics,
    decision_window,
)
from backend.app.snapshot import GenerationRecord, parse_timestamp, write_snapshot
from backend.app.storage import read_snapshot

DECISION_DATE = date(2026, 1, 1)
HOUR = parse_timestamp("2026-01-02T00:00:00Z")
CUTOFF = parse_timestamp("2026-01-01T09:00:00Z")


def record(delivery=HOUR, published=CUTOFF, value=100):
    return GenerationRecord(delivery, published, value)


def actual_pair(delivery=HOUR, first=100, second=100):
    return [
        record(delivery, delivery + timedelta(minutes=30), first),
        record(delivery + timedelta(minutes=30), delivery + timedelta(hours=1), second),
    ]


def test_latest_eligible_forecast_includes_cutoff_and_excludes_one_microsecond_later():
    forecasts = [
        record(published=CUTOFF + timedelta(microseconds=1), value=999),
        record(published=CUTOFF, value=120),
        record(published=CUTOFF - timedelta(hours=1), value=110),
    ]
    result = analyze_day(DECISION_DATE, actual_pair(), forecasts)
    interval = result.intervals[0]
    assert interval.forecast_mw == 120
    assert interval.forecast_published_at == CUTOFF
    assert interval.actual_mw == 100
    assert interval.error_mw == 20
    assert result.metrics.sample_count == 1
    assert result.metrics.mae_mw == 20


def test_forecast_published_only_after_cutoff_remains_missing():
    result = analyze_day(DECISION_DATE, actual_pair(), [
        record(published=CUTOFF + timedelta(minutes=30)),
    ])
    assert result.intervals[0].forecast_mw is None
    assert result.intervals[0].forecast_published_at is None
    assert result.intervals[0].actual_mw == 100
    assert result.intervals[0].error_mw is None
    assert result.coverage.forecast_hours == 0
    assert result.coverage.actual_hours == 1
    assert result.coverage.matched_hours == 0


def test_actuals_use_latest_snapshot_revision_even_when_published_after_decision():
    actuals = actual_pair(first=80, second=100)
    actuals.append(record(published=HOUR + timedelta(days=2), value=120))
    result = analyze_day(DECISION_DATE, actuals, [record(value=115)])
    interval = result.intervals[0]
    assert interval.actual_mw == 110
    assert interval.error_mw == 5
    assert interval.actual_publication_times == (
        HOUR + timedelta(days=2), HOUR + timedelta(hours=1),
    )
    assert result.coverage.available_actual_half_hours == 2


def test_partial_actual_hour_is_not_averaged_or_filled():
    first = actual_pair(first=80)[0]
    result = analyze_day(DECISION_DATE, [first], [record(value=100)])
    assert len(result.intervals) == 24
    assert result.intervals[0].actual_mw is None
    assert result.intervals[0].error_mw is None
    assert result.intervals[0].actual_publication_times == (first.published_at, None)
    assert result.intervals[1].forecast_mw is None
    assert result.intervals[1].actual_mw is None
    assert result.coverage.available_actual_half_hours == 1
    assert result.coverage.actual_hours == 0
    assert result.metrics.mae_mw is None
    assert result.metrics.bias_mw is None
    assert result.metrics.rmse_mw is None


def test_zero_generation_and_zero_error_are_valid_matched_values():
    result = analyze_day(DECISION_DATE, actual_pair(first=0, second=0), [record(value=0)])
    assert result.intervals[0].actual_mw == 0
    assert result.intervals[0].error_mw == 0
    assert result.coverage.matched_hours == 1
    assert result.metrics.mae_mw == result.metrics.bias_mw == result.metrics.rmse_mw == 0
    assert result.largest_overforecasts == []


def test_identical_duplicates_do_not_inflate_coverage():
    actuals = actual_pair()
    forecast = record()
    result = analyze_day(DECISION_DATE, actuals + actuals, [forecast, forecast])
    assert result.coverage.available_actual_half_hours == 2
    assert result.coverage.matched_hours == 1


def test_conflicting_duplicate_is_rejected_even_if_a_newer_revision_exists():
    with pytest.raises(ValueError, match="Conflicting generation revisions"):
        analyze_day(DECISION_DATE, [], [
            record(published=CUTOFF - timedelta(hours=1), value=100),
            record(published=CUTOFF, value=120),
            record(published=CUTOFF - timedelta(hours=1), value=110),
        ])


def test_metrics_match_hand_calculation_and_use_identical_samples():
    result = calculate_metrics([3, -4, None, 0])
    assert result.sample_count == 3
    assert result.mae_mw == pytest.approx(7 / 3)
    assert result.bias_mw == pytest.approx(-1 / 3)
    assert result.rmse_mw == pytest.approx(math.sqrt(25 / 3))


@pytest.mark.parametrize("errors,bias", [([2, 4], 3), ([-2, -4], -3)])
def test_bias_sign_distinguishes_overforecast_and_underforecast(errors, bias):
    result = calculate_metrics(errors)
    assert result.bias_mw == bias
    assert result.mae_mw == 3
    assert result.rmse_mw == pytest.approx(math.sqrt(10))


@pytest.mark.parametrize("invalid", [float("nan"), float("inf")])
def test_nonfinite_errors_are_rejected(invalid):
    with pytest.raises(ValueError, match="Errors must be finite"):
        calculate_metrics([invalid])


def test_no_pairs_retains_all_delivery_hours_with_unavailable_metrics():
    result = analyze_day(DECISION_DATE, [], [])
    assert len(result.intervals) == 24
    assert result.coverage.expected_actual_half_hours == 48
    assert result.coverage.matched_hours == result.metrics.sample_count == 0
    assert result.metrics.mae_mw is result.metrics.bias_mw is result.metrics.rmse_mw is None
    assert all(interval.error_mw is None for interval in result.intervals)


def test_largest_overforecasts_are_positive_top_five_with_stable_time_ties():
    errors = [8, 0, -10, 8, 7, 6, 5, 4]
    actuals = []
    forecasts = []
    for offset, error in enumerate(errors):
        hour = HOUR + timedelta(hours=offset)
        actuals.extend(actual_pair(hour))
        forecasts.append(record(hour, value=100 + error))
    result = analyze_day(DECISION_DATE, actuals, reversed(forecasts))
    assert [i.error_mw for i in result.largest_overforecasts] == [8, 8, 7, 6, 5]
    assert result.largest_overforecasts[0].delivery_start == HOUR
    assert result.largest_overforecasts[1].delivery_start == HOUR + timedelta(hours=3)


def test_january_31_maps_to_february_1_and_excludes_next_midnight():
    cutoff, start, end = decision_window(date(2026, 1, 31), time(0))
    assert cutoff == parse_timestamp("2026-01-31T00:00:00Z")
    assert start == parse_timestamp("2026-02-01T00:00:00Z")
    assert end == parse_timestamp("2026-02-02T00:00:00Z")
    result = analyze_day(date(2026, 1, 31), actual_pair(start) + actual_pair(end), [
        record(start, published=cutoff), record(end, published=cutoff),
    ], cutoff_time=time(0))
    assert result.delivery_date == date(2026, 2, 1)
    assert result.intervals[-1].delivery_end == end
    assert result.coverage.forecast_hours == 1
    assert result.coverage.available_actual_half_hours == 2
    assert result.decision_timezone == "Europe/London"


@pytest.mark.parametrize("invalid", [date(2025, 12, 31), date(2026, 2, 1), datetime(2026, 1, 1)])
def test_unsupported_decision_dates_are_rejected(invalid):
    with pytest.raises(ValueError, match="Decision date"):
        decision_window(invalid)


@pytest.mark.parametrize("invalid", [time(9, 0, 1), time(9, 0, 0, 1), time(9, tzinfo=timezone.utc)])
def test_cutoff_requires_a_minute_precision_local_wall_clock_time(invalid):
    with pytest.raises(ValueError, match="Cutoff"):
        decision_window(DECISION_DATE, invalid)


def test_month_pools_errors_instead_of_averaging_daily_metrics():
    hours = [HOUR, HOUR + timedelta(days=1), HOUR + timedelta(days=1, hours=1)]
    actuals = [row for hour in hours for row in actual_pair(hour)]
    forecasts = [record(hour, value=value) for hour, value in zip(hours, [106, 100, 100])]
    result = analyze_month(iter(actuals), iter(forecasts))
    assert len(result.daily_results) == 31
    assert result.coverage.expected_hours == 744
    assert result.coverage.expected_actual_half_hours == 1488
    assert result.coverage.matched_hours == result.metrics.sample_count == 3
    assert result.metrics.mae_mw == 2
    assert result.metrics.bias_mw == 2
    assert result.metrics.rmse_mw == pytest.approx(math.sqrt(12))
    assert result.daily_results[0].metrics.mae_mw == 6
    assert result.daily_results[1].metrics.mae_mw == 0
    assert result.daily_results[2].metrics.mae_mw is None


def test_month_applies_each_decisions_cutoff_instead_of_end_of_month():
    result = analyze_month([], [
        record(published=CUTOFF - timedelta(minutes=30), value=100),
        record(published=CUTOFF + timedelta(minutes=30), value=999),
        record(HOUR + timedelta(days=1), published=CUTOFF + timedelta(days=1), value=200),
    ])
    assert result.daily_results[0].intervals[0].forecast_mw == 100
    assert result.daily_results[1].intervals[0].forecast_mw == 200


def test_missing_snapshot_fails_without_creating_a_database(tmp_path):
    path = tmp_path / "missing.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        read_snapshot(path)
    assert not path.exists()


def test_storage_reads_native_revisions_and_embedded_provenance_without_writes(tmp_path):
    path = tmp_path / "snapshot.sqlite"
    forecasts = [record(value=100), record(published=CUTOFF + timedelta(minutes=30), value=110)]
    write_snapshot(path, actual_pair(), forecasts, {"source": "fixture"})
    before = path.read_bytes()
    snapshot = read_snapshot(path)
    assert snapshot.actuals == actual_pair()
    assert snapshot.forecasts == forecasts
    assert snapshot.source == {"source": "fixture"}
    assert path.read_bytes() == before


@pytest.mark.parametrize("cutoff,matched", [(time(9), 744), (time(0), 682)])
def test_real_snapshot_month_respects_cutoffs_and_expected_coverage(cutoff, matched):
    snapshot = read_snapshot()
    result = analyze_month(snapshot.actuals, snapshot.forecasts, cutoff_time=cutoff)
    assert result.coverage.actual_hours == 744
    assert result.coverage.available_actual_half_hours == 1488
    assert result.coverage.forecast_hours == result.coverage.matched_hours == matched
    assert result.metrics.sample_count == matched
    for day in result.daily_results:
        assert len(day.intervals) == 24
        assert day.intervals == sorted(day.intervals, key=lambda interval: interval.delivery_start)
        assert all(interval.forecast_published_at <= day.decision_cutoff_at
                   for interval in day.intervals if interval.forecast_published_at is not None)
