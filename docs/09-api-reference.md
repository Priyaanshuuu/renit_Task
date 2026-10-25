# Analysis API: Step 4

Implemented and checked on 25 October 2026. FastAPI exposes the existing [Step 3 calculations](08-analysis-calculations.md) over the bundled read-only snapshot. Dashboard integration remains in Step 5.

Start both development servers using [the root README](../README.md). The API is available directly at `http://127.0.0.1:8000`, and `/api` requests through Vite at `http://127.0.0.1:5173` are proxied to it. Interactive documentation is at `http://127.0.0.1:8000/docs`; the generated contract is `/openapi.json` on the backend.

## Endpoints

All endpoints use `GET`, with query parameters and no request body.

| Path | Inputs | Successful result |
| --- | --- | --- |
| `/api/health` | None | `{"status":"ok","snapshot_ready":true}` when snapshot records and provenance can be read |
| `/api/analysis` | Required `decision_date`; optional `cutoff_time` | Complete daily interval grid, selected publications, coverage, metrics, top overforecasts, and source details |
| `/api/monthly-summary` | Optional `cutoff_time` | Retrospective January aggregate and 31 compact daily summaries |
| `/api/analysis.csv` | Same query model as daily JSON | Attachment containing the same 24 hourly interval results |

Examples:

```text
/api/analysis?decision_date=2026-01-15
/api/analysis?decision_date=2026-01-31&cutoff_time=00%3A00
/api/monthly-summary?cutoff_time=09%3A00
/api/analysis.csv?decision_date=2026-01-15&cutoff_time=09%3A00
```

`decision_date` must use `YYYY-MM-DD`, be a real calendar date, and fall in 1-31 January 2026. Compact dates, timestamps, and dates outside that window are rejected.

`cutoff_time` must have exactly five characters in `HH:MM` form, with valid hours/minutes. Default: `09:00 Europe/London`, an illustrative assumption rather than a confirmed market deadline. Seconds, offsets, whitespace, `9:00`, and `24:00` are rejected. The daily/CSV and monthly query models reject unknown fields; a misspelled cutoff cannot silently fall back to the default. Monthly analysis is fixed to January, so arbitrary month/date filters are not accepted.

## JSON contract

Daily responses contain:

- `decision_date`, `delivery_date`, effective UTC `decision_cutoff_at`, and `decision_timezone`.
- `intervals`: all delivery hours in order, including unavailable values. Each contains `delivery_start`, `delivery_end`, `forecast_mw`, `forecast_published_at`, `actual_mw`, `actual_publication_times`, and `error_mw`.
- `actual_publication_times`: two positions corresponding to native actuals at `H` and `H+30min`, with nulls for missing samples.
- `coverage`: expected, forecast-available, actual-complete, and matched hours, plus expected/available native actual half-hours.
- `metrics`: `sample_count`, `mae_mw`, `bias_mw`, and `rmse_mw`, using the same matched periods.
- `largest_overforecasts`: up to five positive-error periods with deterministic ordering.
- `source`: compact provenance and limitations described below.

Units are MW. Timestamps include UTC `Z`. Missing values are JSON `null`; zero is a valid observation. No matched pairs means count zero and null metrics. No numeric display rounding occurs in the API.

Monthly responses contain `decision_month`, `cutoff_time`, `decision_timezone`, `retrospective: true`, aggregate `coverage`, pooled `metrics`, monthly `largest_overforecasts`, and `source`. `daily_results` has 31 entries with decision/delivery dates, effective cutoff, coverage, and metrics. It omits each day's interval array to keep the summary compact. Each daily decision still uses its own cutoff; monthly metrics do not average daily metrics.

The API returns actuals and outcome-derived metrics. Decision view will hide them until reveal in Step 5; this is a UI workflow, not an access-control boundary.

## Source details and assumptions

`source` includes provider, attribution, snapshot `built_at`, earliest/latest recorded retrieval timestamps, delivery bounds, MW units, comparison interval, publication extraction windows for both datasets, the alignment rule, and limitations. Delivery end is exclusive; publication extraction end is inclusive. The earliest/latest retrieval timestamps summarize the recorded requests, not continuous monitoring or a live freshness guarantee. Raw response arrays, all 66 request URLs, and local filesystem paths are not returned.

The data remains the snapshot from Step 2. Actual corrections published after the extraction window are not guaranteed. Hourly comparison treats each WINDFOR label as the following hour and requires both actual half-hours. See [the source reference](07-data-snapshot.md) for evidence and limitations.

## CSV contract

CSV is UTF-8 `text/csv`, with a `Content-Disposition` attachment filename such as `wind-analysis-2026-01-15-0900.csv`. There is one header row and one row for every delivery hour, including gaps.

Columns include decision/delivery dates, cutoff and timezone, interval start/end, `published_at` (the JSON `forecast_published_at`), forecast/actual/error MW, each native actual publication time, units, provider, snapshot/retrieval timestamps, alignment rule, attribution, extraction windows, and limitations. Missing values are empty cells. Real zeros remain numeric cells. Source text is quoted by the standard CSV writer when required.

CSV uses the same validated daily response as JSON, including timestamps and null handling. It contains no independent forecast-selection or metric implementation.

## Failures and readiness

| Situation | Status and behavior |
| --- | --- |
| Valid day, including partial coverage or no matched pairs | `200`; explicit counts and null unavailable values |
| Invalid or unknown query input | `422`; FastAPI's normal `detail` validation list |
| Missing/unreadable/incompatible SQLite file or malformed required source metadata | `503`; `{"detail":"Analysis data is unavailable."}` |
| Unknown API path | JSON `404` |
| Unexpected calculation or response-contract bug | `500`; generic server message, without private diagnostics |

Validation completes before snapshot loading for the analysis routes. A bad query remains `422` even if the snapshot is missing. Expected storage/provenance failures are translated at the HTTP boundary and logged server-side; arbitrary calculation exceptions are not turned into empty success responses.

Health now checks snapshot readiness as well as API response availability. It reads the supported schema, native record types/grids/timestamps, and required provenance. It does not promise complete coverage, new source data, or authenticated production acceptance. A readable snapshot can contain missing observations. There is no startup download, scheduler, or request-time call to Elexon.

Unexpected `500` responses may be plain text from the framework. Step 5's client must handle validation lists, ordinary error strings, and a generic fallback for non-JSON responses.

## Configuration and code ownership

The default snapshot path is resolved from the module location. Optional `WIND_SNAPSHOT_PATH` can point to a different artifact; absolute paths are used directly and relative paths are resolved from the project root. For example, set it before starting Uvicorn:

```powershell
$env:WIND_SNAPSHOT_PATH = "data/wind_snapshot.sqlite"
```

`routes.py` owns HTTP handlers, safe error translation, provenance summarization, and CSV formatting. `schemas.py` owns input/response contracts and reuses the existing typed calculation dataclasses for nested results. `storage.py` owns read-only SQLite connections and validation of native records. `analysis.py` remains independent of FastAPI. Routes performing local reads/calculations use synchronous `def` so FastAPI runs them outside its async event loop.

The API loads this bounded snapshot per request and closes each SQLite connection before calculating results. It adds no database server, shared connection pool, cache service, settings package, or dependency upgrades. Query/response patterns follow official [FastAPI query models](https://fastapi.tiangolo.com/tutorial/query-param-models/), [response models](https://fastapi.tiangolo.com/tutorial/response-model/), and [Pydantic dataclass support](https://docs.pydantic.dev/latest/concepts/dataclasses/).

## Verification

**97 tests passed** across snapshot preparation, calculation, storage, and API behavior. API checks cover strict inputs, default and changed cutoffs, exact-cutoff selection, null gaps/zeros, compact monthly output, JSON/CSV agreement, safe `503`, readiness, invalid-query precedence, environment configuration, unknown routes, unexpected `500`, finite results, and OpenAPI content types.

Live local HTTP checks passed directly against Uvicorn and through Vite: readiness, daily JSON/CSV at 09:00 and midnight, retrospective monthly output, `422`, and `404`. The real daily result matches Step 3: 15 January has MAE 782.75 MW and first-hour error +62.5 MW. Midnight monthly analysis has 682 matched hours. The snapshot checksum remained unchanged.

The pinned Starlette version emits one deprecation warning about HTTPX use in `TestClient`. Tests work with the installed dependencies; no dependency migration was performed as part of this step. Browser dashboard workflows, Docker, and deployed-app acceptance remain unverified.
