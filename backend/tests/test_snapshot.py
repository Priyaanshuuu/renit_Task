import json
import sqlite3
from contextlib import closing
from datetime import timedelta

import httpx
import pytest

from backend.app.snapshot import (
    DELIVERY_START,
    GenerationRecord,
    coverage_report,
    normalize_records,
    parse_timestamp,
    utc_text,
    write_snapshot,
)
from backend.scripts.build_snapshot import download_rows, fetch_dataset


def source_row(dataset="WINDFOR", **overrides):
    return {
        "dataset": dataset,
        "fuelType": "WIND",
        "startTime": "2026-01-02T00:00:00Z",
        "publishTime": "2026-01-01T07:30:00Z",
        "generation": 1000,
        **overrides,
    }


def test_normalizes_offsets_filters_fuels_and_excludes_delivery_end():
    result = normalize_records("FUELHH", [
        source_row("FUELHH", startTime="2026-01-02T01:00:00+01:00"),
        source_row("FUELHH", fuelType="CCGT"),
        source_row("FUELHH", startTime="2026-02-02T00:00:00Z"),
    ])
    assert len(result.records) == 1
    assert result.records[0].delivery_start == DELIVERY_START
    assert result.counts["other_fuels"] == 1
    assert result.counts["outside_delivery"] == 1


def test_collapses_identical_duplicates_but_preserves_publication_revisions():
    original = source_row()
    result = normalize_records("WINDFOR", [
        original, original.copy(),
        source_row(publishTime="2026-01-01T09:30:00Z", generation=1100),
    ])
    assert len(result.records) == 2
    assert result.counts["identical_duplicates"] == 1
    assert [r.generation_mw for r in result.records] == [1000, 1100]


def test_conflicting_duplicate_fails_instead_of_choosing_arbitrary_value():
    with pytest.raises(ValueError, match="Conflicting WINDFOR duplicate"):
        normalize_records("WINDFOR", [source_row(), source_row(generation=999)])


@pytest.mark.parametrize("value", [None, True, "1000", float("nan"), float("inf")])
def test_invalid_generation_is_not_silently_coerced_or_filled(value):
    with pytest.raises(ValueError, match="generation"):
        normalize_records("WINDFOR", [source_row(generation=value)])


@pytest.mark.parametrize("value", [None, "invalid", "2026-01-01T09:00:00"])
def test_requires_valid_timezone_aware_source_timestamps(value):
    with pytest.raises(ValueError):
        parse_timestamp(value)


def test_fixed_timestamp_precision_preserves_sqlite_cutoff_ordering():
    cutoff = DELIVERY_START
    later = cutoff + timedelta(microseconds=1)
    assert utc_text(cutoff).endswith(".000000Z")
    assert utc_text(cutoff) < utc_text(later)
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("CREATE TABLE publications (published_at TEXT)")
        connection.executemany("INSERT INTO publications VALUES (?)", [
            (utc_text(later),), (utc_text(cutoff),),
        ])
        assert connection.execute(
            "SELECT published_at FROM publications WHERE published_at <= ?",
            (utc_text(cutoff),),
        ).fetchall() == [(utc_text(cutoff),)]


@pytest.mark.parametrize("dataset,delivery", [
    ("WINDFOR", "2026-01-02T00:30:00Z"),
    ("FUELHH", "2026-01-02T00:15:00Z"),
])
def test_rejects_changed_source_resolution(dataset, delivery):
    with pytest.raises(ValueError, match="delivery grid"):
        normalize_records(dataset, [source_row(dataset, startTime=delivery)])


def test_missing_half_hour_does_not_count_as_complete_actual_hour():
    actuals = normalize_records("FUELHH", [source_row("FUELHH")])
    forecasts = normalize_records("WINDFOR", [source_row()])
    report = coverage_report(actuals, forecasts)
    first_day = report["daily_coverage"][0]
    assert first_day["available_actual_half_hours"] == 1
    assert first_day["complete_actual_hours"] == 0
    assert first_day["forecast_hours_at_00_00"] == 0
    assert first_day["forecast_hours_at_09_00"] == 1
    assert len(first_day["missing_actual_half_hours"]) == 47
    assert report["daily_coverage"][-1]["decision_date"] == "2026-01-31"
    assert report["daily_coverage"][-1]["delivery_date"] == "2026-02-01"


def test_empty_source_is_an_explicit_failure():
    with pytest.raises(ValueError, match="No usable WINDFOR"):
        normalize_records("WINDFOR", [])


def test_sqlite_is_readable_in_read_only_mode_and_keeps_metadata(tmp_path):
    path = tmp_path / "snapshot.sqlite"
    actual = GenerationRecord(DELIVERY_START, DELIVERY_START, 1234.0)
    forecast = GenerationRecord(DELIVERY_START, DELIVERY_START - timedelta(days=1), 1200.0)
    report = {"units": "MW", "requests": []}
    write_snapshot(path, [actual], [forecast], report)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        assert connection.execute("SELECT actual_mw FROM wind_actuals").fetchone() == (1234,)
        assert connection.execute("SELECT forecast_mw FROM wind_forecasts").fetchone() == (1200,)
        assert json.loads(connection.execute(
            "SELECT value FROM snapshot_metadata WHERE key='report'"
        ).fetchone()[0]) == report
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM wind_actuals")


def test_failed_candidate_does_not_replace_existing_snapshot(tmp_path):
    path = tmp_path / "snapshot.sqlite"
    record = GenerationRecord(DELIVERY_START, DELIVERY_START, 1000)
    write_snapshot(path, [record], [record], {})
    previous_bytes = path.read_bytes()
    with pytest.raises(sqlite3.IntegrityError):
        write_snapshot(path, [record, record], [record], {})
    assert path.read_bytes() == previous_bytes
    assert not list(tmp_path.glob("*.tmp"))


def test_publication_filters_cache_and_offline_rebuild(tmp_path):
    def respond(request):
        assert parse_timestamp(request.url.params["publishDateTimeFrom"]) == DELIVERY_START
        assert parse_timestamp(request.url.params["publishDateTimeTo"]) == DELIVERY_START + timedelta(days=1)
        return httpx.Response(200, json=[source_row(publishTime=utc_text(DELIVERY_START))])

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        rows, requests = fetch_dataset(
            client, "WINDFOR", DELIVERY_START, DELIVERY_START + timedelta(days=1),
            tmp_path, False, False,
        )

    def reject_network(request):
        pytest.fail("Offline rebuild attempted a network call")

    with httpx.Client(transport=httpx.MockTransport(reject_network)) as client:
        cached_rows, cached_requests = fetch_dataset(
            client, "WINDFOR", DELIVERY_START, DELIVERY_START + timedelta(days=1),
            tmp_path, True, False,
        )
    assert cached_rows == rows
    assert cached_requests == requests


def test_response_outside_requested_publication_window_is_not_cached(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=[source_row()])
    )) as client:
        with pytest.raises(ValueError, match="escaped publication filter"):
            fetch_dataset(
                client, "WINDFOR", DELIVERY_START, DELIVERY_START + timedelta(days=1),
                tmp_path, False, False,
            )
    assert not list(tmp_path.rglob("*.json"))


def test_permanent_http_failure_is_not_retried():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(400, json={"detail": "Bad parameters"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            download_rows(client, "https://example.test", {})
    assert len(requests) == 1


def test_transient_failure_retries_with_a_bound(monkeypatch):
    requests = []
    delays = []
    monkeypatch.setattr("backend.scripts.build_snapshot.time.sleep", delays.append)

    def respond(request):
        requests.append(request)
        if len(requests) < 3:
            return httpx.Response(503, headers={"Retry-After": "1"})
        return httpx.Response(200, json=[source_row()])

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert download_rows(client, "https://example.test", {}) == [source_row()]
    assert delays == [1, 1]
    assert len(requests) == 3


def test_long_retry_after_does_not_retry_earlier_than_server_requests():
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(429, headers={"Retry-After": "120"})
    )) as client:
        with pytest.raises(httpx.HTTPStatusError):
            download_rows(client, "https://example.test", {})
