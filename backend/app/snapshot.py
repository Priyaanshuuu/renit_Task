"""Validate native wind records and build the historical SQLite snapshot."""

import json
import math
import sqlite3
import tempfile
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

DELIVERY_START = datetime(2026, 1, 2, tzinfo=timezone.utc)
DELIVERY_END = datetime(2026, 2, 2, tzinfo=timezone.utc)
FORECAST_PUBLICATION_START = datetime(2025, 12, 29, tzinfo=timezone.utc)
FORECAST_PUBLICATION_END = datetime(2026, 2, 1, tzinfo=timezone.utc)
ACTUAL_PUBLICATION_START = DELIVERY_START
ACTUAL_PUBLICATION_END = datetime(2026, 2, 3, tzinfo=timezone.utc)


@dataclass(frozen=True, order=True)
class GenerationRecord:
    delivery_start: datetime
    published_at: datetime
    generation_mw: float


@dataclass
class NormalizedRecords:
    records: list[GenerationRecord]
    counts: dict[str, int]


def utc_text(value: datetime) -> str:
    """Use fixed precision so SQLite timestamp ordering matches time ordering."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Cannot serialize a timestamp without a timezone")
    return value.astimezone(timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"Expected an ISO timestamp, received {value!r}")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {value!r}") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"Timestamp has no timezone: {value!r}")
    return result.astimezone(timezone.utc)


def normalize_records(
    dataset: str, rows: list[dict[str, object]]
) -> NormalizedRecords:
    if dataset not in {"FUELHH", "WINDFOR"}:
        raise ValueError(f"Unsupported dataset: {dataset}")
    counts = Counter(
        received=len(rows), other_fuels=0, outside_delivery=0,
        identical_duplicates=0,
    )
    by_key: dict[tuple[datetime, datetime], GenerationRecord] = {}
    interval_minutes = 30 if dataset == "FUELHH" else 60
    for row in rows:
        if row.get("dataset") != dataset:
            raise ValueError(f"Unexpected dataset field in {dataset}: {row!r}")
        if dataset == "FUELHH":
            if not isinstance(row.get("fuelType"), str):
                raise ValueError("FUELHH record has no fuelType")
            if row["fuelType"] != "WIND":
                counts["other_fuels"] += 1
                continue
        delivery_start = parse_timestamp(row.get("startTime"))
        published_at = parse_timestamp(row.get("publishTime"))
        if not DELIVERY_START <= delivery_start < DELIVERY_END:
            counts["outside_delivery"] += 1
            continue
        if (delivery_start.minute % interval_minutes
                or delivery_start.second or delivery_start.microsecond):
            raise ValueError(f"Unexpected {dataset} delivery grid: {delivery_start}")
        value = row.get("generation")
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)):
            raise ValueError(f"Invalid {dataset} generation: {value!r}")
        record = GenerationRecord(delivery_start, published_at, float(value))
        key = (delivery_start, published_at)
        previous = by_key.get(key)
        if previous is not None:
            if previous.generation_mw != record.generation_mw:
                raise ValueError(f"Conflicting {dataset} duplicate at {key}")
            counts["identical_duplicates"] += 1
            continue
        by_key[key] = record
    if not by_key:
        raise ValueError(f"No usable {dataset} records for the delivery window")
    counts["stored"] = len(by_key)
    return NormalizedRecords(sorted(by_key.values()), dict(counts))


def coverage_report(
    actuals: NormalizedRecords, forecasts: NormalizedRecords
) -> dict[str, object]:
    """Count availability only; do not select revisions or calculate errors."""
    actual_times = {row.delivery_start for row in actuals.records}
    forecast_times = {row.delivery_start for row in forecasts.records}
    publications: dict[datetime, list[datetime]] = {}
    for row in forecasts.records:
        publications.setdefault(row.delivery_start, []).append(row.published_at)
    daily = []
    for offset in range((DELIVERY_END - DELIVERY_START).days):
        day = DELIVERY_START + timedelta(days=offset)
        decision_day = day - timedelta(days=1)
        half_hours = [day + timedelta(minutes=30 * n) for n in range(48)]
        hours = half_hours[::2]
        complete_hours = [hour for hour in hours
                          if hour in actual_times
                          and hour + timedelta(minutes=30) in actual_times]
        # January's London wall-clock times equal UTC. These counts describe
        # availability only; selection and metric calculations belong to Step 3.
        available_at_midnight = {
            hour for hour in hours
            if any(pub <= decision_day for pub in publications.get(hour, []))
        }
        available_at_nine = {
            hour for hour in hours
            if any(pub <= decision_day + timedelta(hours=9)
                   for pub in publications.get(hour, []))
        }
        daily.append({
            "decision_date": decision_day.date().isoformat(),
            "delivery_date": day.date().isoformat(),
            "expected_actual_half_hours": 48,
            "available_actual_half_hours": sum(t in actual_times for t in half_hours),
            "expected_comparison_hours": 24,
            "complete_actual_hours": len(complete_hours),
            "forecast_hours_any_publication": sum(t in forecast_times for t in hours),
            "forecast_hours_at_00_00": len(available_at_midnight),
            "forecast_hours_at_09_00": len(available_at_nine),
            "missing_forecast_hours_at_00_00": [
                utc_text(t) for t in hours if t not in available_at_midnight
            ],
            "missing_forecast_hours_at_09_00": [
                utc_text(t) for t in hours if t not in available_at_nine
            ],
            "missing_actual_half_hours": [utc_text(t) for t in half_hours
                                          if t not in actual_times],
            "missing_forecast_hours": [utc_text(t) for t in hours
                                       if t not in forecast_times],
        })
    revision_counts = Counter(row.delivery_start for row in forecasts.records)
    return {
        "delivery_start_inclusive": utc_text(DELIVERY_START),
        "delivery_end_exclusive": utc_text(DELIVERY_END),
        "timezone": "Europe/London",
        "units": "MW",
        "actual_interval_minutes": 30,
        "forecast_resolution_minutes": 60,
        "comparison_interval_minutes": 60,
        "alignment_rule": (
            "Pair forecast at hour H with mean actual MW at H and H+30min; "
            "require both actuals. Treat the hourly forecast as representing "
            "[H,H+1h) for this pilot; this is a comparison assumption, not an "
            "interval-end field supplied by WINDFOR. No interpolation or gap fill."
        ),
        "actuals": {
            **actuals.counts,
            "expected_delivery_intervals": 1488,
            "available_delivery_intervals": len(actual_times),
            "additional_publication_revisions": len(actuals.records) - len(actual_times),
        },
        "forecasts": {
            **forecasts.counts,
            "expected_delivery_hours": 744,
            "available_delivery_hours": len(forecast_times),
            "publication_count": len({r.published_at for r in forecasts.records}),
            "revisions_per_hour_min": min(revision_counts.values()),
            "revisions_per_hour_max": max(revision_counts.values()),
            "earliest_publication": utc_text(min(r.published_at for r in forecasts.records)),
            "latest_publication": utc_text(max(r.published_at for r in forecasts.records)),
        },
        "daily_coverage": daily,
        "limitations": [
            "Only publication windows recorded in requests were extracted; "
            "later-published actual corrections are not guaranteed to be included.",
            "Publication time is the availability proxy; historic receipt/network "
            "latency is unknown.",
            "Coverage is for GB operationally metered national wind, not all UK "
            "or embedded wind and not a customer's own generation.",
            "Hourly comparison loses half-hour detail and assumes forecast "
            "hour labels represent the following hour.",
        ],
    }


def write_snapshot(
    path: Path,
    actuals: list[GenerationRecord],
    forecasts: list[GenerationRecord],
    report: dict[str, object],
) -> None:
    """Validate a candidate database before atomically replacing the snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as file:
        candidate = Path(file.name)
    try:
        with closing(sqlite3.connect(candidate)) as connection:
            with connection:
                for table, value_column, records in (
                    ("wind_actuals", "actual_mw", actuals),
                    ("wind_forecasts", "forecast_mw", forecasts),
                ):
                    # Identifiers are fixed literals above; values are parameterized.
                    connection.execute(f"""
                        CREATE TABLE {table} (
                            delivery_start TEXT NOT NULL,
                            published_at TEXT NOT NULL,
                            {value_column} REAL NOT NULL,
                            PRIMARY KEY (delivery_start, published_at)
                        ) WITHOUT ROWID
                    """)
                    connection.executemany(
                        f"INSERT INTO {table} VALUES (?, ?, ?)",
                        [(utc_text(r.delivery_start), utc_text(r.published_at),
                          r.generation_mw) for r in records],
                    )
                connection.execute(
                    "CREATE TABLE snapshot_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO snapshot_metadata VALUES (?, ?)",
                    ("report", json.dumps(report, allow_nan=False, sort_keys=True)),
                )
                connection.execute("PRAGMA user_version = 1")
            if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("Candidate snapshot failed SQLite integrity check")
        candidate.replace(path)
    finally:
        candidate.unlink(missing_ok=True)
