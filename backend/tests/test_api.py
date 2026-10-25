import csv
import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import date, timedelta
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from backend.app import routes
from backend.app.analysis import ErrorMetrics, analyze_day, analyze_month
from backend.app.main import app
from backend.app.snapshot import GenerationRecord, parse_timestamp, write_snapshot
from backend.app.storage import DEFAULT_SNAPSHOT_PATH, read_snapshot


@pytest.fixture
def snapshot_path(tmp_path):
    path = tmp_path / "fixture.sqlite"
    hour = parse_timestamp("2026-01-02T00:00:00Z")
    cutoff = parse_timestamp("2026-01-01T09:00:00Z")
    actuals = [
        GenerationRecord(hour, hour + timedelta(minutes=30), 100),
        GenerationRecord(hour + timedelta(minutes=30), hour + timedelta(hours=1), 120),
        GenerationRecord(hour + timedelta(hours=1), hour + timedelta(minutes=90), 0),
    ]
    forecasts = [
        GenerationRecord(hour, cutoff - timedelta(hours=1), 100),
        GenerationRecord(hour, cutoff, 120),
        GenerationRecord(hour, cutoff + timedelta(microseconds=1), 999),
        GenerationRecord(hour + timedelta(hours=1), cutoff, 0),
    ]
    write_snapshot(path, actuals, forecasts, read_snapshot().source)
    return path


@pytest.fixture
def client(snapshot_path):
    app.dependency_overrides[routes.get_snapshot_path] = lambda: snapshot_path
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_daily_json_preserves_cutoff_selection_gaps_and_provenance(client):
    response = client.get("/api/analysis", params={"decision_date": "2026-01-01"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["delivery_date"] == "2026-01-02"
    assert payload["decision_timezone"] == "Europe/London"
    assert payload["decision_cutoff_at"] == "2026-01-01T09:00:00Z"
    assert len(payload["intervals"]) == 24
    assert payload["intervals"][0]["forecast_mw"] == 120
    assert payload["intervals"][0]["actual_mw"] == 110
    assert payload["intervals"][0]["error_mw"] == 10
    assert payload["intervals"][1]["forecast_mw"] == 0
    assert payload["intervals"][1]["actual_mw"] is None
    assert payload["intervals"][1]["error_mw"] is None
    assert payload["intervals"][2]["forecast_published_at"] is None
    assert payload["coverage"]["available_actual_half_hours"] == 3
    assert payload["metrics"] == {"sample_count": 1, "mae_mw": 10, "bias_mw": 10, "rmse_mw": 10}
    assert payload["source"]["units"] == "MW"
    assert payload["source"]["comparison_interval_minutes"] == 60
    assert len(payload["source"]["publication_windows"]) == 2
    assert payload["source"]["limitations"]
    assert "requests" not in payload["source"]


def test_earlier_cutoff_changes_selection(client):
    payload = client.get("/api/analysis?decision_date=2026-01-01&cutoff_time=08:00").json()
    assert payload["intervals"][0]["forecast_mw"] == 100
    assert payload["metrics"]["bias_mw"] == -10


def test_valid_empty_day_returns_counts_and_null_metrics(client):
    response = client.get("/api/analysis?decision_date=2026-01-02")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["intervals"]) == 24
    assert payload["coverage"]["matched_hours"] == 0
    assert payload["metrics"] == {"sample_count": 0, "mae_mw": None, "bias_mw": None, "rmse_mw": None}


@pytest.mark.parametrize("endpoint", ["/api/analysis", "/api/analysis.csv"])
@pytest.mark.parametrize("params", [
    {},
    {"decision_date": "2026-02-01"},
    {"decision_date": "2025-12-31"},
    {"decision_date": "2026-01-32"},
    {"decision_date": "2026-01-01T00:00:00Z"},
    {"decision_date": "20260101"},
    {"decision_date": "2026-01-01", "cutoff_time": "24:00"},
    {"decision_date": "2026-01-01", "cutoff_time": "09:60"},
    {"decision_date": "2026-01-01", "cutoff_time": "09:00:00"},
    {"decision_date": "2026-01-01", "cutoff_time": "09:00Z"},
    {"decision_date": "2026-01-01", "cutoff_time": "9:00"},
    {"decision_date": "2026-01-01", "cutoff_time": "09:00\n"},
    {"decision_date": "2026-01-01", "cutoff": "08:00"},
])
def test_daily_and_csv_reject_invalid_or_unknown_inputs(client, endpoint, params):
    response = client.get(endpoint, params=params)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize("query", ["cutoff_time=09:00:00", "decision_date=2026-01-01", "month=2026-02"])
def test_monthly_rejects_invalid_or_unsupported_filters(client, query):
    assert client.get("/api/monthly-summary?" + query).status_code == 422


def test_monthly_response_is_retrospective_and_compact(client, snapshot_path):
    snapshot = read_snapshot(snapshot_path)
    expected = analyze_month(snapshot.actuals, snapshot.forecasts)
    response = client.get("/api/monthly-summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["retrospective"] is True
    assert payload["cutoff_time"] == "09:00"
    assert len(payload["daily_results"]) == 31
    assert payload["daily_results"][-1]["delivery_date"] == "2026-02-01"
    assert "intervals" not in payload["daily_results"][0]
    assert payload["coverage"]["matched_hours"] == expected.coverage.matched_hours
    assert payload["metrics"]["mae_mw"] == expected.metrics.mae_mw


def test_csv_agrees_with_daily_json_and_preserves_blanks_and_zero(client):
    query = {"decision_date": "2026-01-01"}
    payload = client.get("/api/analysis", params=query).json()
    response = client.get("/api/analysis.csv", params=query)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="wind-analysis-2026-01-01-0900.csv"'
    rows = list(csv.DictReader(StringIO(response.text)))
    assert len(rows) == len(payload["intervals"]) == 24
    for row, interval in zip(rows, payload["intervals"]):
        assert row["decision_cutoff_at"] == payload["decision_cutoff_at"]
        assert row["delivery_start"] == interval["delivery_start"]
        assert row["published_at"] == (interval["forecast_published_at"] or "")
        for field in ("forecast_mw", "actual_mw", "error_mw"):
            if interval[field] is None:
                assert row[field] == ""
            else:
                assert float(row[field]) == interval[field]
        assert row["units"] == "MW"
        assert row["attribution"] == payload["source"]["attribution"]
        assert row["actual_publication_end"] == payload["source"]["publication_windows"][0]["publication_end"]
    assert float(rows[1]["forecast_mw"]) == 0
    assert rows[1]["actual_mw"] == ""
    assert rows[1]["actual_second_published_at"] == ""


@pytest.mark.parametrize("endpoint", [
    "/api/health", "/api/analysis?decision_date=2026-01-01", "/api/monthly-summary",
    "/api/analysis.csv?decision_date=2026-01-01",
])
def test_unavailable_snapshot_returns_safe_503(client, tmp_path, endpoint):
    missing = tmp_path / "private-missing.sqlite"
    app.dependency_overrides[routes.get_snapshot_path] = lambda: missing
    response = client.get(endpoint)
    assert response.status_code == 503
    assert response.json() == {"detail": "Analysis data is unavailable."}
    assert str(missing) not in response.text
    assert not missing.exists()


def test_validation_precedes_snapshot_access(client, tmp_path):
    app.dependency_overrides[routes.get_snapshot_path] = lambda: tmp_path / "missing.sqlite"
    assert client.get("/api/analysis?decision_date=2026-02-01").status_code == 422


def test_health_checks_snapshot_readability_and_metadata(client, snapshot_path):
    assert client.get("/api/health").json() == {"status": "ok", "snapshot_ready": True}
    with closing(sqlite3.connect(snapshot_path)) as db:
        report = json.loads(db.execute("SELECT value FROM snapshot_metadata").fetchone()[0])
        report["units"] = "MWh"
        db.execute("UPDATE snapshot_metadata SET value = ?", (json.dumps(report),))
        db.commit()
    assert client.get("/api/health").status_code == 503


def test_invalid_snapshot_values_fail_readiness(client, snapshot_path):
    with closing(sqlite3.connect(snapshot_path)) as db:
        db.execute("UPDATE wind_actuals SET actual_mw = ?", ("invalid",))
        db.commit()
    assert client.get("/api/health").status_code == 503


def test_environment_snapshot_path_is_used(client, snapshot_path, monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setenv("WIND_SNAPSHOT_PATH", str(snapshot_path))
    payload = client.get("/api/analysis?decision_date=2026-01-01").json()
    assert payload["metrics"]["mae_mw"] == 10


def test_unknown_api_is_json_404(client):
    response = client.get("/api/unknown")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_unexpected_analysis_bug_is_not_hidden_as_missing_data(client, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("private diagnostic")

    monkeypatch.setattr(routes, "analyze_day", fail)
    response = client.get("/api/analysis?decision_date=2026-01-01")
    assert response.status_code == 500
    assert "private diagnostic" not in response.text


def test_nonfinite_server_results_do_not_leak_into_json(client, snapshot_path, monkeypatch):
    snapshot = read_snapshot(snapshot_path)
    result = analyze_day(date(2026, 1, 1), snapshot.actuals, snapshot.forecasts)
    broken = replace(result, metrics=ErrorMetrics(1, float("inf"), 10, 10))
    monkeypatch.setattr(routes, "analyze_day", lambda *args, **kwargs: broken)
    assert client.get("/api/analysis?decision_date=2026-01-01").status_code == 500


def test_openapi_documents_queries_json_contract_and_csv(client):
    paths = client.get("/openapi.json").json()["paths"]
    query = paths["/api/analysis"]["get"]
    assert "requestBody" not in query
    assert {param["name"] for param in query["parameters"]} == {"decision_date", "cutoff_time"}
    assert "application/json" in query["responses"]["200"]["content"]
    assert "503" in query["responses"]
    assert set(paths["/api/analysis.csv"]["get"]["responses"]["200"]["content"]) == {"text/csv"}


def test_real_api_matches_step3_and_does_not_mutate_snapshot(client):
    app.dependency_overrides.clear()
    before = hashlib.sha256(DEFAULT_SNAPSHOT_PATH.read_bytes()).hexdigest()
    daily = client.get("/api/analysis?decision_date=2026-01-15").json()
    assert daily["metrics"]["mae_mw"] == 782.75
    assert daily["intervals"][0]["error_mw"] == 62.5
    assert daily["source"]["publication_windows"][0]["publication_end"] == "2026-02-03T00:00:00Z"
    month = client.get("/api/monthly-summary?cutoff_time=00:00").json()
    assert month["coverage"]["matched_hours"] == 682
    assert month["metrics"]["sample_count"] == 682
    assert hashlib.sha256(DEFAULT_SNAPSHOT_PATH.read_bytes()).hexdigest() == before
