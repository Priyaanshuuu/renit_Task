"""Run from the repository root: python -m backend.scripts.build_snapshot."""

import argparse
import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from ..app.snapshot import (
    ACTUAL_PUBLICATION_END,
    ACTUAL_PUBLICATION_START,
    FORECAST_PUBLICATION_END,
    FORECAST_PUBLICATION_START,
    coverage_report,
    normalize_records,
    parse_timestamp,
    utc_text,
    write_snapshot,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
logger = logging.getLogger(__name__)


def download_rows(
    client: httpx.Client, url: str, params: dict[str, str]
) -> list[dict[str, object]]:
    for attempt in range(3):
        try:
            response = client.get(url, params=params)
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                retry_after = response.headers.get("Retry-After", "")
                delay = 2 ** attempt
                if retry_after.isdigit():
                    delay = int(retry_after)
                elif retry_after:
                    try:
                        delay = max(0, (
                            parsedate_to_datetime(retry_after)
                            - datetime.now(timezone.utc)
                        ).total_seconds())
                    except (TypeError, ValueError, OverflowError):
                        logger.warning("Ignoring invalid Retry-After header")
                # Do not retry earlier than a long server-requested delay.
                if delay > 30:
                    response.raise_for_status()
                logger.warning("Transient HTTP %s; retrying in %ss", response.status_code, delay)
                time.sleep(delay)
                continue
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
                raise ValueError("Expected a JSON array of dataset records")
            return rows
        except httpx.TransportError:
            if attempt == 2:
                raise
            logger.warning("Network error; retrying request", exc_info=False)
            time.sleep(2 ** attempt)
    raise RuntimeError("Request retry loop exited unexpectedly")


def fetch_dataset(
    client: httpx.Client,
    dataset: str,
    start: datetime,
    end: datetime,
    cache_dir: Path,
    offline: bool,
    refresh: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows = []
    requests = []
    cursor = start
    while cursor < end:
        window_end = min(cursor + timedelta(days=1), end)
        params = {
            # Query boundaries are whole UTC midnights; retain this URL format
            # independently of the fixed microsecond precision used in SQLite.
            "publishDateTimeFrom": cursor.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "publishDateTimeTo": window_end.isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        url = f"{BASE_URL}/{dataset}/stream"
        request_url = str(httpx.Request("GET", url, params=params).url)
        cache_file = cache_dir / dataset / f"{cursor.date()}.json"
        if cache_file.exists() and not refresh:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"Invalid cached response: {cache_file}")
            if payload.get("url") != request_url:
                raise ValueError(f"Cached request does not match: {cache_file}")
            if not isinstance(payload.get("records"), list):
                raise ValueError(f"Invalid cached response: {cache_file}")
            parse_timestamp(payload.get("retrieved_at"))
            logger.info("%s %s: cached %s rows", dataset, cursor.date(), len(payload["records"]))
        else:
            if offline:
                raise ValueError(f"Offline cache is missing: {cache_file}")
            downloaded = download_rows(client, url, params)
            payload = {
                "url": request_url,
                "retrieved_at": utc_text(datetime.now(timezone.utc)),
                "records": downloaded,
            }
            # Validate response publication filtering before trusting/caching it.
            for record in payload["records"]:
                if not cursor <= parse_timestamp(record.get("publishTime")) <= window_end:
                    raise ValueError(f"Response escaped publication filter: {request_url}")
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
            temporary.replace(cache_file)
            logger.info("%s %s: downloaded %s rows", dataset, cursor.date(), len(payload["records"]))
        records = payload["records"]
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"Invalid record in {cache_file}")
            if not cursor <= parse_timestamp(record.get("publishTime")) <= window_end:
                raise ValueError(f"Cached response escaped publication filter: {cache_file}")
        rows.extend(records)
        requests.append({
            "dataset": dataset,
            "url": request_url,
            "retrieved_at": payload["retrieved_at"],
            "response_rows": len(records),
            "response_sha256": hashlib.sha256(
                json.dumps(records, sort_keys=True, separators=(",", ":"),
                           allow_nan=False).encode("utf-8")
            ).hexdigest(),
        })
        cursor = window_end
    return rows, requests


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data/wind_snapshot.sqlite")
    parser.add_argument("--cache-dir", type=Path, default=PROJECT_ROOT / "data/raw")
    cache_mode = parser.add_mutually_exclusive_group()
    cache_mode.add_argument("--offline", action="store_true", help="Use cached responses only")
    cache_mode.add_argument("--refresh", action="store_true", help="Download every response again")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
            actual_rows, actual_requests = fetch_dataset(
                client, "FUELHH", ACTUAL_PUBLICATION_START, ACTUAL_PUBLICATION_END,
                args.cache_dir, args.offline, args.refresh,
            )
            forecast_rows, forecast_requests = fetch_dataset(
                client, "WINDFOR", FORECAST_PUBLICATION_START, FORECAST_PUBLICATION_END,
                args.cache_dir, args.offline, args.refresh,
            )
        actuals = normalize_records("FUELHH", actual_rows)
        forecasts = normalize_records("WINDFOR", forecast_rows)
        report = coverage_report(actuals, forecasts)
        report.update({
            "schema_version": 1,
            "built_at": utc_text(datetime.now(timezone.utc)),
            "source": "Elexon Insights Solution / National Energy System Operator",
            "attribution": "Contains BMRS data © Elexon Limited copyright and database right 2026.",
            "requests": actual_requests + forecast_requests,
        })
        write_snapshot(args.output, actuals.records, forecasts.records, report)
        # The metadata inside SQLite is authoritative if a sidecar write fails.
        report_path = args.output.with_suffix(".report.json")
        temporary = report_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(report_path)
        logger.info("Snapshot: %s", args.output)
        logger.info("Coverage: %s actual half-hours; %s forecast hours; %s forecast revisions",
                    report["actuals"]["available_delivery_intervals"],
                    report["forecasts"]["available_delivery_hours"], len(forecasts.records))
    except (httpx.HTTPError, ValueError, OSError, sqlite3.Error) as exc:
        logger.error("Snapshot build failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
