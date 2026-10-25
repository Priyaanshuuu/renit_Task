"""Decision-time forecast selection and retrospective wind error calculations."""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .snapshot import GenerationRecord

DECISION_START_DATE = date(2026, 1, 1)
DECISION_END_DATE = date(2026, 1, 31)
DECISION_TIMEZONE = "Europe/London"
DEFAULT_CUTOFF_TIME = time(9)
COMPARISON_INTERVAL = timedelta(hours=1)
ACTUAL_INTERVAL = timedelta(minutes=30)


@dataclass(frozen=True)
class ErrorMetrics:
    sample_count: int
    mae_mw: float | None
    bias_mw: float | None
    rmse_mw: float | None


@dataclass(frozen=True)
class Coverage:
    expected_hours: int
    forecast_hours: int
    actual_hours: int
    matched_hours: int
    expected_actual_half_hours: int
    available_actual_half_hours: int


@dataclass(frozen=True)
class IntervalResult:
    delivery_start: datetime
    delivery_end: datetime
    forecast_mw: float | None
    forecast_published_at: datetime | None
    actual_mw: float | None
    # Publication times for H and H+30min, in that order, including gaps.
    actual_publication_times: tuple[datetime | None, datetime | None]
    error_mw: float | None


@dataclass(frozen=True)
class DailyAnalysis:
    decision_date: date
    delivery_date: date
    decision_cutoff_at: datetime
    decision_timezone: str
    intervals: list[IntervalResult]
    coverage: Coverage
    metrics: ErrorMetrics
    largest_overforecasts: list[IntervalResult]


@dataclass(frozen=True)
class MonthlyAnalysis:
    decision_month: str
    cutoff_time: time
    decision_timezone: str
    daily_results: list[DailyAnalysis]
    coverage: Coverage
    metrics: ErrorMetrics
    largest_overforecasts: list[IntervalResult]


def decision_window(
    decision_date: date, cutoff_time: time = DEFAULT_CUTOFF_TIME
) -> tuple[datetime, datetime, datetime]:
    """Return the UTC decision cutoff and half-open next-day delivery bounds."""
    if isinstance(decision_date, datetime) or not isinstance(decision_date, date):
        raise ValueError("Decision date must be a calendar date")
    if not DECISION_START_DATE <= decision_date <= DECISION_END_DATE:
        raise ValueError("Decision date must be in January 2026")
    if (not isinstance(cutoff_time, time) or cutoff_time.tzinfo is not None
            or cutoff_time.second or cutoff_time.microsecond):
        raise ValueError("Cutoff must be a local HH:MM time without an offset")
    london = ZoneInfo(DECISION_TIMEZONE)
    delivery_date = decision_date + timedelta(days=1)
    cutoff = datetime.combine(decision_date, cutoff_time, tzinfo=london)
    start = datetime.combine(delivery_date, time.min, tzinfo=london)
    end = datetime.combine(delivery_date + timedelta(days=1), time.min, tzinfo=london)
    return (
        cutoff.astimezone(timezone.utc),
        start.astimezone(timezone.utc),
        end.astimezone(timezone.utc),
    )


def _latest_records(
    records: Iterable[GenerationRecord],
    start: datetime,
    end: datetime,
    cutoff: datetime | None = None,
) -> dict[datetime, GenerationRecord]:
    """Filter eligibility before choosing revisions; never use input order."""
    latest: dict[datetime, GenerationRecord] = {}
    seen: dict[tuple[datetime, datetime], float] = {}
    for record in records:
        if not start <= record.delivery_start < end:
            continue
        if cutoff is not None and record.published_at > cutoff:
            continue
        if not math.isfinite(record.generation_mw):
            raise ValueError("Generation must be finite")
        key = (record.delivery_start, record.published_at)
        if key in seen and seen[key] != record.generation_mw:
            raise ValueError(f"Conflicting generation revisions at {key}")
        seen[key] = record.generation_mw
        previous = latest.get(record.delivery_start)
        if previous is None or record.published_at > previous.published_at:
            latest[record.delivery_start] = record
    return latest


def calculate_metrics(errors: Iterable[float | None]) -> ErrorMetrics:
    """All metrics use the same matched samples; None is missing, zero is valid."""
    matched = [error for error in errors if error is not None]
    if not matched:
        return ErrorMetrics(0, None, None, None)
    if not all(math.isfinite(error) for error in matched):
        raise ValueError("Errors must be finite")
    count = len(matched)
    return ErrorMetrics(
        sample_count=count,
        mae_mw=math.fsum(abs(error) for error in matched) / count,
        bias_mw=math.fsum(matched) / count,
        rmse_mw=math.sqrt(math.fsum(error * error for error in matched) / count),
    )


def _largest_overforecasts(intervals: list[IntervalResult]) -> list[IntervalResult]:
    positive = [interval for interval in intervals
                if interval.error_mw is not None and interval.error_mw > 0]
    # Break ties by delivery time to keep the result deterministic.
    return sorted(
        positive,
        key=lambda interval: (
            -(interval.error_mw if interval.error_mw is not None else 0),
            interval.delivery_start,
        ),
    )[:5]


def analyze_day(
    decision_date: date,
    actuals: Iterable[GenerationRecord],
    forecasts: Iterable[GenerationRecord],
    *,
    cutoff_time: time = DEFAULT_CUTOFF_TIME,
) -> DailyAnalysis:
    cutoff, start, end = decision_window(decision_date, cutoff_time)
    selected_forecasts = _latest_records(forecasts, start, end, cutoff)
    # Actuals are retrospective: use the latest revision within this snapshot,
    # including publications after the decision. Never apply that rule to forecasts.
    selected_actuals = _latest_records(actuals, start, end)
    intervals = []
    cursor = start
    while cursor < end:
        forecast = selected_forecasts.get(cursor)
        first = selected_actuals.get(cursor)
        second = selected_actuals.get(cursor + ACTUAL_INTERVAL)
        actual_mw = (
            (first.generation_mw + second.generation_mw) / 2
            if first is not None and second is not None else None
        )
        forecast_mw = forecast.generation_mw if forecast is not None else None
        error_mw = (
            forecast_mw - actual_mw
            if forecast_mw is not None and actual_mw is not None else None
        )
        intervals.append(IntervalResult(
            delivery_start=cursor,
            delivery_end=cursor + COMPARISON_INTERVAL,
            forecast_mw=forecast_mw,
            forecast_published_at=forecast.published_at if forecast is not None else None,
            actual_mw=actual_mw,
            actual_publication_times=(
                first.published_at if first is not None else None,
                second.published_at if second is not None else None,
            ),
            error_mw=error_mw,
        ))
        cursor += COMPARISON_INTERVAL
    metrics = calculate_metrics(interval.error_mw for interval in intervals)
    return DailyAnalysis(
        decision_date=decision_date,
        delivery_date=decision_date + timedelta(days=1),
        decision_cutoff_at=cutoff,
        decision_timezone=DECISION_TIMEZONE,
        intervals=intervals,
        coverage=Coverage(
            expected_hours=len(intervals),
            forecast_hours=sum(i.forecast_mw is not None for i in intervals),
            actual_hours=sum(i.actual_mw is not None for i in intervals),
            matched_hours=metrics.sample_count,
            expected_actual_half_hours=len(intervals) * 2,
            available_actual_half_hours=len(selected_actuals),
        ),
        metrics=metrics,
        largest_overforecasts=_largest_overforecasts(intervals),
    )


def analyze_month(
    actuals: Iterable[GenerationRecord],
    forecasts: Iterable[GenerationRecord],
    *,
    cutoff_time: time = DEFAULT_CUTOFF_TIME,
) -> MonthlyAnalysis:
    """Evaluate each January decision separately, then pool matched hourly errors."""
    actual_records = list(actuals)
    forecast_records = list(forecasts)
    days = [
        analyze_day(
            DECISION_START_DATE + timedelta(days=offset),
            actual_records, forecast_records, cutoff_time=cutoff_time,
        )
        for offset in range((DECISION_END_DATE - DECISION_START_DATE).days + 1)
    ]
    intervals = [interval for day in days for interval in day.intervals]
    return MonthlyAnalysis(
        decision_month="2026-01",
        cutoff_time=cutoff_time,
        decision_timezone=DECISION_TIMEZONE,
        daily_results=days,
        coverage=Coverage(
            expected_hours=sum(day.coverage.expected_hours for day in days),
            forecast_hours=sum(day.coverage.forecast_hours for day in days),
            actual_hours=sum(day.coverage.actual_hours for day in days),
            matched_hours=sum(day.coverage.matched_hours for day in days),
            expected_actual_half_hours=sum(
                day.coverage.expected_actual_half_hours for day in days
            ),
            available_actual_half_hours=sum(
                day.coverage.available_actual_half_hours for day in days
            ),
        ),
        metrics=calculate_metrics(interval.error_mw for interval in intervals),
        largest_overforecasts=_largest_overforecasts(intervals),
    )
