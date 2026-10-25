"""Read the prepared snapshot without creating files or sharing connections."""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from .snapshot import GenerationRecord, parse_timestamp

DEFAULT_SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data/wind_snapshot.sqlite"


@dataclass(frozen=True)
class SnapshotData:
    actuals: list[GenerationRecord]
    forecasts: list[GenerationRecord]
    source: dict[str, object]


def read_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> SnapshotData:
    """Load the bounded pilot data; close the read-only connection before returning."""
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        if connection.execute("PRAGMA user_version").fetchone() != (1,):
            raise ValueError("Unsupported snapshot schema version")
        actual_rows = connection.execute(
            "SELECT delivery_start, published_at, actual_mw FROM wind_actuals "
            "ORDER BY delivery_start, published_at"
        ).fetchall()
        forecast_rows = connection.execute(
            "SELECT delivery_start, published_at, forecast_mw FROM wind_forecasts "
            "ORDER BY delivery_start, published_at"
        ).fetchall()
        metadata = connection.execute(
            "SELECT value FROM snapshot_metadata WHERE key = ?", ("report",)
        ).fetchone()
    if metadata is None:
        raise ValueError("Snapshot source metadata is missing")
    source = json.loads(metadata[0])
    if not isinstance(source, dict):
        raise ValueError("Snapshot source metadata must be an object")
    return SnapshotData(
        actuals=[GenerationRecord(parse_timestamp(start), parse_timestamp(published), value)
                 for start, published, value in actual_rows],
        forecasts=[GenerationRecord(parse_timestamp(start), parse_timestamp(published), value)
                   for start, published, value in forecast_rows],
        source=source,
    )
