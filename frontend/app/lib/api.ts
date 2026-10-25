export interface Coverage {
  expected_hours: number;
  forecast_hours: number;
  actual_hours: number;
  matched_hours: number;
  expected_actual_half_hours: number;
  available_actual_half_hours: number;
}
export interface Metrics {
  sample_count: number;
  mae_mw: number | null;
  bias_mw: number | null;
  rmse_mw: number | null;
}
export interface Interval {
  delivery_start: string;
  delivery_end: string;
  forecast_mw: number | null;
  forecast_published_at: string | null;
  actual_mw: number | null;
  error_mw: number | null;
}
export interface Source {
  provider: string;
  attribution: string;
  built_at: string;
  retrieval_finished_at: string;
  alignment_rule: string;
  limitations: string[];
}
export interface Analysis {
  decision_date: string;
  delivery_date: string;
  decision_cutoff_at: string;
  decision_timezone: string;
  coverage: Coverage;
  metrics: Metrics;
  intervals: Interval[];
  largest_overforecasts: Interval[];
  source: Source;
}
export interface MonthlySummary {
  decision_month: string;
  cutoff_time: string;
  retrospective: boolean;
  coverage: Coverage;
  metrics: Metrics;
}
export type ApiResult<T> =
  { data: T; error?: never } | { error: string; data?: never };

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
function nullableNumber(value: unknown): value is number | null {
  return value === null || finite(value);
}
function timestamp(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}
function calendarDate(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    timestamp(value) &&
    new Date(value).toISOString().slice(0, 10) === value
  );
}
function coverage(value: unknown): value is Coverage {
  return (
    record(value) &&
    [
      "expected_hours",
      "forecast_hours",
      "actual_hours",
      "matched_hours",
      "expected_actual_half_hours",
      "available_actual_half_hours",
    ].every((key) => Number.isInteger(value[key]) && Number(value[key]) >= 0)
  );
}
function metrics(value: unknown): value is Metrics {
  return (
    record(value) &&
    Number.isInteger(value.sample_count) &&
    Number(value.sample_count) >= 0 &&
    ["mae_mw", "bias_mw", "rmse_mw"].every((key) => nullableNumber(value[key]))
  );
}
function interval(value: unknown): value is Interval {
  return (
    record(value) &&
    timestamp(value.delivery_start) &&
    timestamp(value.delivery_end) &&
    ["forecast_mw", "actual_mw", "error_mw"].every((key) =>
      nullableNumber(value[key]),
    ) &&
    (value.forecast_published_at === null ||
      timestamp(value.forecast_published_at))
  );
}
function source(value: unknown): value is Source {
  return (
    record(value) &&
    ["provider", "attribution", "alignment_rule"].every(
      (key) => typeof value[key] === "string",
    ) &&
    timestamp(value.built_at) &&
    timestamp(value.retrieval_finished_at) &&
    Array.isArray(value.limitations) &&
    value.limitations.every((item) => typeof item === "string")
  );
}
function analysis(value: unknown): value is Analysis {
  return (
    record(value) &&
    calendarDate(value.decision_date) &&
    calendarDate(value.delivery_date) &&
    timestamp(value.decision_cutoff_at) &&
    value.decision_timezone === "Europe/London" &&
    coverage(value.coverage) &&
    metrics(value.metrics) &&
    source(value.source) &&
    Array.isArray(value.intervals) &&
    value.intervals.every(interval) &&
    Array.isArray(value.largest_overforecasts) &&
    value.largest_overforecasts.every(interval)
  );
}
function monthlySummary(value: unknown): value is MonthlySummary {
  return (
    record(value) &&
    value.decision_month === "2026-01" &&
    typeof value.cutoff_time === "string" &&
    value.retrospective === true &&
    coverage(value.coverage) &&
    metrics(value.metrics)
  );
}

async function get<T>(
  path: string,
  signal: AbortSignal,
  valid: (value: unknown) => value is T,
): Promise<ApiResult<T>> {
  try {
    const response = await fetch(path, {
      signal,
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      if (response.status === 422)
        return {
          error:
            "Choose a January 2026 decision date and a valid cutoff time (HH:MM).",
        };
      if (response.status === 503)
        return {
          error:
            "Analysis data is unavailable. Check that the prepared snapshot is readable, then retry.",
        };
      return { error: "The analysis request failed. Please retry." };
    }
    const value: unknown = await response.json();
    return valid(value)
      ? { data: value }
      : { error: "The API returned an unexpected response. Please retry." };
  } catch (error) {
    if (signal.aborted) throw error;
    return {
      error:
        "Could not load analysis data. Check the API connection, then retry.",
    };
  }
}
export function analysisQuery(decisionDate: string, cutoffTime: string) {
  return new URLSearchParams({
    decision_date: decisionDate,
    cutoff_time: cutoffTime,
  }).toString();
}
export function fetchAnalysis(
  decisionDate: string,
  cutoffTime: string,
  signal: AbortSignal,
) {
  return get(
    `/api/analysis?${analysisQuery(decisionDate, cutoffTime)}`,
    signal,
    analysis,
  );
}
export function fetchMonthlySummary(cutoffTime: string, signal: AbortSignal) {
  return get(
    `/api/monthly-summary?${new URLSearchParams({ cutoff_time: cutoffTime })}`,
    signal,
    monthlySummary,
  );
}
