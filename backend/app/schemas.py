import re
from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from .analysis import (
    DECISION_END_DATE, DECISION_START_DATE, DEFAULT_CUTOFF_TIME,
    Coverage, ErrorMetrics, IntervalResult,
)


class CutoffQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cutoff_time: str = Field(
        default=DEFAULT_CUTOFF_TIME.strftime("%H:%M"),
        min_length=5, max_length=5,
        pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$",
        description="Local HH:MM time in Europe/London; illustrative default, not a market deadline.",
    )


class AnalysisQuery(CutoffQuery):
    decision_date: date = Field(
        ge=DECISION_START_DATE, le=DECISION_END_DATE,
        description="January 2026 buying decision date, formatted YYYY-MM-DD.",
    )

    @field_validator("decision_date", mode="before")
    @classmethod
    def require_iso_date(cls, value: object) -> object:
        if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
            raise ValueError("Decision date must use YYYY-MM-DD")
        return value


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, allow_inf_nan=False)


class HealthResponse(ResponseModel):
    status: Literal["ok"]
    snapshot_ready: Literal[True] = Field(
        description="Snapshot schema, native tables, and provenance are readable; coverage may be partial."
    )


class ErrorResponse(BaseModel):
    detail: str


class PublicationWindow(ResponseModel):
    dataset: Literal["FUELHH", "WINDFOR"]
    publication_start: AwareDatetime
    publication_end: AwareDatetime = Field(description="Inclusive extraction boundary.")


class SourceResponse(ResponseModel):
    provider: str = Field(validation_alias="source")
    attribution: str
    built_at: AwareDatetime
    retrieval_started_at: AwareDatetime
    retrieval_finished_at: AwareDatetime
    delivery_start: AwareDatetime = Field(validation_alias="delivery_start_inclusive")
    delivery_end: AwareDatetime = Field(
        validation_alias="delivery_end_exclusive", description="Exclusive delivery boundary."
    )
    units: Literal["MW"]
    comparison_interval_minutes: Literal[60]
    publication_windows: list[PublicationWindow]
    alignment_rule: str
    limitations: list[str]


class DailySummaryResponse(ResponseModel):
    decision_date: date
    delivery_date: date
    decision_cutoff_at: AwareDatetime
    coverage: Coverage
    metrics: ErrorMetrics = Field(description="Matched hourly sample count and errors in MW.")


class AnalysisResponse(DailySummaryResponse):
    decision_timezone: Literal["Europe/London"]
    intervals: list[IntervalResult] = Field(description="All delivery hours, including null gaps; values in MW.")
    largest_overforecasts: list[IntervalResult]
    source: SourceResponse


class MonthlySummaryResponse(ResponseModel):
    decision_month: Literal["2026-01"]
    cutoff_time: str
    decision_timezone: Literal["Europe/London"]
    retrospective: Literal[True] = True
    daily_results: list[DailySummaryResponse]
    coverage: Coverage
    metrics: ErrorMetrics = Field(description="Pooled matched hourly errors in MW, not averaged daily metrics.")
    largest_overforecasts: list[IntervalResult]
    source: SourceResponse
