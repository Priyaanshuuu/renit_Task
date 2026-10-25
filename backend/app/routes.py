import csv
import logging
import os
import sqlite3
from dataclasses import asdict
from datetime import time
from io import StringIO
from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from .analysis import analyze_day, analyze_month
from .schemas import (
    AnalysisQuery,
    AnalysisResponse,
    CutoffQuery,
    DailySummaryResponse,
    ErrorResponse,
    HealthResponse,
    MonthlySummaryResponse,
    PublicationWindow,
    SourceResponse,
)
from .snapshot import parse_timestamp
from .storage import DEFAULT_SNAPSHOT_PATH, SnapshotData, read_snapshot

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
UNAVAILABLE_RESPONSE = {503: {"model": ErrorResponse, "description": "Analysis snapshot is unavailable."}}


def get_snapshot_path() -> Path:
    """Resolve local configuration without opening files during input validation."""
    configured = os.environ.get("WIND_SNAPSHOT_PATH")
    if configured is None:
        return DEFAULT_SNAPSHOT_PATH
    path = Path(configured)
    return path if path.is_absolute() else DEFAULT_SNAPSHOT_PATH.parents[1] / path


def _source_response(report: dict[str, object]) -> SourceResponse:
    requests = report.get("requests")
    if not isinstance(requests, list) or not requests:
        raise ValueError("Snapshot request provenance is missing")
    retrieved = []
    windows = []
    for dataset in ("FUELHH", "WINDFOR"):
        starts, ends = [], []
        for request in requests:
            if not isinstance(request, dict):
                raise ValueError("Invalid snapshot request provenance")
            if request.get("dataset") != dataset:
                continue
            url = request.get("url")
            if not isinstance(url, str):
                raise ValueError("Snapshot source URL is missing")
            params = parse_qs(urlsplit(url).query)
            start = params.get("publishDateTimeFrom", [])
            end = params.get("publishDateTimeTo", [])
            if len(start) != 1 or len(end) != 1:
                raise ValueError("Snapshot publication range is missing")
            starts.append(parse_timestamp(start[0]))
            ends.append(parse_timestamp(end[0]))
            if starts[-1] > ends[-1]:
                raise ValueError("Snapshot publication range is reversed")
            retrieved.append(parse_timestamp(request.get("retrieved_at")))
        if not starts:
            raise ValueError(f"Snapshot provenance is missing {dataset}")
        windows.append(PublicationWindow(
            dataset=dataset, publication_start=min(starts), publication_end=max(ends),
        ))
    return SourceResponse.model_validate({
        **report,
        "publication_windows": windows,
        "retrieval_started_at": min(retrieved),
        "retrieval_finished_at": max(retrieved),
    })


def _load_snapshot(path: Path) -> tuple[SnapshotData, SourceResponse]:
    try:
        snapshot = read_snapshot(path)
        source = _source_response(snapshot.source)
    except (OSError, sqlite3.Error, ValueError) as exc:
        logger.warning("Analysis snapshot is unavailable", exc_info=True)
        raise HTTPException(status_code=503, detail="Analysis data is unavailable.") from exc
    return snapshot, source


def _daily_response(query: AnalysisQuery, path: Path) -> AnalysisResponse:
    snapshot, source = _load_snapshot(path)
    result = analyze_day(
        query.decision_date, snapshot.actuals, snapshot.forecasts,
        cutoff_time=time.fromisoformat(query.cutoff_time),
    )
    return AnalysisResponse.model_validate({**asdict(result), "source": source})


@router.get(
    "/health",
    tags=["Health"],
    summary="Check API and snapshot readiness",
    description="Checks readable snapshot schema, records, and provenance. Does not promise complete observation coverage.",
    responses=UNAVAILABLE_RESPONSE,
)
def get_health(path: Annotated[Path, Depends(get_snapshot_path)]) -> HealthResponse:
    _load_snapshot(path)
    return HealthResponse(status="ok", snapshot_ready=True)


@router.get(
    "/analysis", tags=["Analysis"], summary="Analyze one January buying decision",
    description="Latest eligible forecast per next-day hour, retrospective actuals, matched error metrics, and source details. All generation/error values are MW.",
    responses=UNAVAILABLE_RESPONSE,
)
def get_analysis(
    query: Annotated[AnalysisQuery, Query()],
    path: Annotated[Path, Depends(get_snapshot_path)],
) -> AnalysisResponse:
    return _daily_response(query, path)


@router.get(
    "/monthly-summary", tags=["Analysis"], summary="Summarize January decisions retrospectively",
    description="Applies the chosen cutoff separately to each decision day and pools matched hourly errors. Daily results are compact summaries; values are MW.",
    responses=UNAVAILABLE_RESPONSE,
)
def get_monthly_summary(
    query: Annotated[CutoffQuery, Query()],
    path: Annotated[Path, Depends(get_snapshot_path)],
) -> MonthlySummaryResponse:
    snapshot, source = _load_snapshot(path)
    result = analyze_month(
        snapshot.actuals, snapshot.forecasts,
        cutoff_time=time.fromisoformat(query.cutoff_time),
    )
    return MonthlySummaryResponse(
        decision_month=result.decision_month,
        cutoff_time=query.cutoff_time,
        decision_timezone=result.decision_timezone,
        daily_results=[DailySummaryResponse.model_validate(day) for day in result.daily_results],
        coverage=result.coverage,
        metrics=result.metrics,
        largest_overforecasts=result.largest_overforecasts,
        source=source,
    )


@router.get(
    "/analysis.csv", tags=["Analysis"], summary="Download the daily analysis as CSV",
    response_class=Response,
    responses={
        **UNAVAILABLE_RESPONSE,
        200: {"description": "One row per delivery hour; missing values are blank.",
              "content": {"text/csv": {"schema": {"type": "string"}}}},
    },
)
def download_analysis_csv(
    query: Annotated[AnalysisQuery, Query()],
    path: Annotated[Path, Depends(get_snapshot_path)],
) -> Response:
    payload = _daily_response(query, path).model_dump(mode="json")
    source = payload["source"]
    windows = {window["dataset"]: window for window in source["publication_windows"]}
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "decision_date", "delivery_date", "decision_cutoff_at", "decision_timezone",
        "delivery_start", "delivery_end", "published_at", "forecast_mw", "actual_mw",
        "error_mw", "actual_first_published_at", "actual_second_published_at", "units",
        "source", "source_built_at", "retrieval_started_at", "retrieval_finished_at",
        "alignment_rule", "attribution", "actual_publication_start", "actual_publication_end",
        "forecast_publication_start", "forecast_publication_end", "limitations",
    ])
    for interval in payload["intervals"]:
        writer.writerow([
            payload["decision_date"], payload["delivery_date"], payload["decision_cutoff_at"],
            payload["decision_timezone"], interval["delivery_start"], interval["delivery_end"],
            interval["forecast_published_at"], interval["forecast_mw"], interval["actual_mw"],
            interval["error_mw"], *interval["actual_publication_times"], source["units"],
            source["provider"], source["built_at"], source["retrieval_started_at"],
            source["retrieval_finished_at"], source["alignment_rule"], source["attribution"],
            windows["FUELHH"]["publication_start"], windows["FUELHH"]["publication_end"],
            windows["WINDFOR"]["publication_start"], windows["WINDFOR"]["publication_end"],
            "; ".join(source["limitations"]),
        ])
    filename = f"wind-analysis-{query.decision_date}-{query.cutoff_time.replace(':', '')}.csv"
    return Response(
        content=output.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
