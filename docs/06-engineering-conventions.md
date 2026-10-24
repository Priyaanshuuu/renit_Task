# Engineering conventions and implementation reference

Reviewed against official documentation on **24 October 2026**. This is guidance for future implementation, not a record of implemented features or production readiness.

Read this alongside [the project steps](steps.md) before writing code. Implementation starts only when the user authorizes the relevant step. Research and documentation updates do not authorize starting it.

## 1. Quality within the pilot scope

Production-quality habits here mean readable names, clear contracts, correct calculations, explicit resource ownership, useful failures, and focused tests. Keep the architecture proportional to one dashboard and one historical snapshot.

The choices below are project defaults derived from the sources linked in each section. Framework documentation explains capabilities; it does not require this exact folder layout, endpoint naming, or business policy. Update a choice when implementation evidence justifies it, and record why.

Keep Python 3.11 and the dependencies in `backend/requirements.txt`. Read documentation compatible with the installed versions; current documentation can describe newer features. Do not upgrade packages or add tools merely because a new example uses them.

## 2. Names and code style

| Area | Convention | Project example |
| --- | --- | --- |
| Python modules, functions, variables | Descriptive `snake_case` | `forecast_selection.py`, `select_available_forecasts` |
| Python classes and Pydantic models | `PascalCase` | `AnalysisResponse`, `IntervalResult` |
| Python constants | `UPPER_SNAKE_CASE` | `DECISION_TIMEZONE` |
| JSON fields and query parameters | `snake_case`, matching Python | `decision_date`, `forecast_mw` |
| SQL tables and columns | Consistent `snake_case` | `wind_forecasts`, `published_at` |
| React components and TypeScript types | `PascalCase` | `ForecastChart`, `AnalysisResponse` |
| TypeScript variables and functions | `camelCase` | `decisionDate`, `fetchAnalysis` |
| API paths | Lowercase resource names; hyphens for multiple words | `/api/monthly-summary` |
| Tests | Describe observable behavior | `test_excludes_forecasts_after_cutoff` |

Python naming follows [PEP 8](https://peps.python.org/pep-0008/#naming-conventions). JSON, SQL, frontend naming, and path conventions are project choices. Keep existing framework filenames such as `root.tsx` and `routes.ts`.

- Use names that carry the domain and unit: `forecast_mw`, `actual_mw`, `error_mw`, `published_at`, `delivery_start`. Distinguish a calendar `decision_date` from an instant `decision_cutoff_at`.
- Map Elexon's source names once at ingestion. For example, `publishTime` becomes `published_at`; preserve the mapping in the data notes. Avoid mixing source casing throughout the app.
- Prefer ordinary functions over classes with no state. Use early returns where they simplify the flow; avoid clever comprehensions for multi-step business rules.
- Annotate function parameters and returns. Use Python 3.11 forms such as `list[IntervalResult]` and `float | None`. Keep DataFrames inside data/analysis code rather than making them the public API contract.
- Explain assumptions and non-obvious rules in docstrings or short comments. Avoid comments that merely restate the code. Keep formatting consistent with the surrounding file.
- Avoid vague modules such as `utils.py`, generic manager classes, wildcard imports, and blanket type suppressions. Extract a helper when it has a clear responsibility or real reuse.

## 3. Small modules with clear ownership

The following is a target shape, not a scaffold to generate now. Add a file only when its responsibility exists; split `analysis.py` later if it actually becomes hard to follow.

```text
backend/
  app/
    __init__.py
    main.py           # App creation, router registration, lifecycle, static files
    routes.py         # HTTP inputs, response models, HTTP error translation
    schemas.py        # Pydantic query and response models
    analysis.py       # Forecast selection, alignment, coverage, metrics
    storage.py        # SQLite queries and connection ownership
  scripts/
    build_snapshot.py # Explicit download and snapshot preparation command
  tests/              # Focused behavior and API tests
  requirements.txt
frontend/              # Existing React Router starter
data/                  # Prepared snapshot and source metadata, added later
```

The dependency direction is straightforward: routes call analysis and storage; analysis does not import FastAPI. Ingestion can reuse analysis/data-validation helpers without starting a web server. Keep downloads out of imports and request handlers.

Use one `APIRouter` for the small API. `Depends` is useful for supplying a configured snapshot path and for test overrides; it is not a reason to introduce a dependency-injection framework. Do not add repositories, interfaces, service classes, or a separate folder for each abstraction by default. [FastAPI's router guidance](https://fastapi.tiangolo.com/tutorial/bigger-applications/) supports composing ordinary Python modules.

## 4. Proposed HTTP contract

These endpoint names are defaults to settle before Step 4 and then use consistently in the frontend, tests, and README. All are read-only `GET` requests; do not put a JSON body on a GET request.

| Endpoint | Inputs | Result |
| --- | --- | --- |
| `/api/health` | None | Small health/readiness result; checks required snapshot availability once the data step exists |
| `/api/analysis` | `decision_date`, optional `cutoff_time` | Selected next-day intervals, coverage, metrics, and provenance |
| `/api/monthly-summary` | Optional `cutoff_time` | Retrospective January summary, applying that cutoff separately to each decision date |
| `/api/analysis.csv` | Same inputs as daily analysis | The same day's interval results as CSV |

Example: `/api/analysis?decision_date=2026-01-15&cutoff_time=09%3A00`.

- `decision_date` is an ISO calendar date restricted to 1-31 January 2026. `cutoff_time` is a local `HH:MM` wall-clock time, default `09:00`, interpreted only in `Europe/London`; reject offsets, seconds, and invalid hours/minutes rather than silently accepting another meaning.
- Use a shared validated query model for daily JSON and CSV inputs. Prefer `Annotated` with FastAPI query declarations. Reject unknown query fields with `extra="forbid"` so a misspelled cutoff is visible. Test the declared format, defaults, and boundary dates. [FastAPI query models](https://fastapi.tiangolo.com/tutorial/query-param-models/).
- Allow the intentional conversion of URL strings into dates and times. Apply strict validation selectively to source values where coercion would conceal bad data; global strict mode can reject legitimate query strings. [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/).
- Declare Pydantic response models. Return ordinary objects that satisfy those models rather than manually assembling JSON strings. Include field descriptions, MW units, and nullability in OpenAPI; use meaningful endpoint summaries and tags. Response validation catches server-side contract errors. [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/).
- Return a direct response object, with clear groups such as `intervals`, `coverage`, `metrics`, and `source`. Avoid a generic `success/data/message` wrapper, duplicate status fields, or pagination for a bounded day's intervals.
- Use UTC ISO 8601 timestamps with an explicit `Z` or `+00:00`. Include the effective `decision_cutoff_at`, delivery date, and decision timezone so callers do not reconstruct assumptions.
- Represent missing values as JSON `null`, never `NaN`, infinity, zero, or a dash string. Keep intervals in delivery order and keep numerical precision for calculations; round for display only.
- CSV uses explicit headers such as `delivery_start`, `published_at`, `forecast_mw`, `actual_mw`, and `error_mw`. Use the standard CSV writer, blank cells for missing values, `text/csv`, and a predictable attachment filename. Reuse analysis results rather than reimplementing selection for export.

The API may include actuals in its analysis response. Decision view hides outcomes in the UI; it does not provide secrecy against someone inspecting the response. This is a retrospective analysis tool, with no outcome-access security requirement.

## 5. Status codes and errors

Use standard HTTP meaning and FastAPI's existing behavior. These mappings are project policy based on [HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html#name-status-codes) and [FastAPI error handling](https://fastapi.tiangolo.com/tutorial/handling-errors/).

| Situation | Response |
| --- | --- |
| Valid analysis, including partial coverage or no matched pairs | `200`, explicit counts, null unavailable values, and an explanation of coverage |
| Invalid format, unsupported decision date, unknown query field | `422`, FastAPI validation detail |
| Unknown API route | `404`; never frontend HTML |
| Expected failure to open/read the required snapshot | `503`, short explanation that analysis data is unavailable |
| Unexpected bug or invalid server response model | `500`, generic client message; diagnostic details stay in logs |

Missing observations in a readable snapshot are different from an unavailable database. A valid empty analysis is not a server failure, and partial coverage does not mean HTTP `206`.

Keep the default `{"detail": ...}` error structure: validation detail is a list; intentional HTTP error detail can be a short string. The frontend must handle both, plus a generic fallback when an unexpected error is not JSON. Do not build an error-envelope framework.

Raise `HTTPException` at the HTTP boundary for expected API failures. Keep analysis functions independent of HTTP. Catch specific storage/network exceptions where recovery or translation is possible; never turn arbitrary exceptions into an empty successful result. Preserve exception context, log unexpected failures once, and keep debug tracebacks out of public responses.

## 6. Time and data correctness

- Use timezone-aware instants for source delivery/publication timestamps and cutoff comparisons. Interpret local decision inputs explicitly using `ZoneInfo("Europe/London")`, then convert to UTC. Do not use the operating system's timezone implicitly. [Python datetime](https://docs.python.org/3.11/library/datetime.html#aware-and-naive-objects), [zoneinfo](https://docs.python.org/3.11/library/zoneinfo.html).
- Derive the delivery day from the next local calendar date. Use a half-open delivery range, `[start, end)`, to avoid counting midnight twice. Do not generalize January's expected 48 half-hours to daylight-saving transition days.
- Filter `published_at <= decision_cutoff_at` before selecting the latest revision per verified delivery interval. Resolve conflicting duplicate keys explicitly; do not let DataFrame row order decide the result.
- Match verified intervals before calculating errors. Build one matched-pair mask for all metrics and coverage; no forward-fill or zero-fill. Use `isna`/`notna` rather than equality checks against missing-value sentinels. [pandas missing data](https://pandas.pydata.org/docs/user_guide/missing_data.html).
- Preserve null actuals, forecasts, and publication times where appropriate. With zero matched pairs, return null MAE, bias, and RMSE. Build monthly metrics from the pooled matched errors, not an unweighted average of daily MAE or RMSE.
- Reject or report malformed/non-finite source numbers and unexpected source schemas. Do not invent a maximum valid generation limit without evidence from the dataset. Keep error sign, units, source coverage, and actuals retrieval date visible.
- Keep forecast eligibility, interval alignment, and metric definitions in one Python implementation shared by daily analysis, monthly summary, and CSV. React formats results; it does not independently recalculate business metrics.

API-filter semantics, revision-history availability, source interval duration, source units, and conflicting duplicates still require real Elexon evidence in Step 2. This research does not establish those facts.

## 7. Resource ownership and execution

**SQLite:** use standard-library `sqlite3` and parameterized SQL. Open the API snapshot with a read-only URI (`mode=ro`, `uri=True`) so a wrong path cannot create an empty database. Create, use, and close a connection inside the same synchronous storage call; do not share a connection between request threads. A connection's `with` block handles transactions but does not close it: use explicit `close()` or `contextlib.closing`. This also avoids relying on newer Python transaction APIs unavailable in 3.11. [Python 3.11 SQLite reference](https://docs.python.org/3.11/library/sqlite3.html).

**Route execution:** use ordinary `def` for routes doing synchronous SQLite and pandas work, so FastAPI dispatches them through its thread pool. Calling a synchronous helper from `async def` does not automatically move it to another thread. Reserve async routes for genuinely awaitable I/O. A thread pool does not solve unlimited CPU work; the bounded snapshot keeps this pilot small. [FastAPI concurrency](https://fastapi.tiangolo.com/async/).

**Lifecycle:** if startup validation or shared resources are needed, use FastAPI's `lifespan` context rather than deprecated startup/shutdown decorators. Keep app imports safe without a downloaded snapshot; perform runtime checks at startup or on the relevant request, as appropriate. Early scaffolding can have process health only; after the snapshot exists, readiness must reflect whether analysis data is usable. [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/).

**Downloads:** use a context-managed synchronous HTTPX client in the preparation script, explicit connect/read timeouts, and `raise_for_status()`. Reuse the client across requests and keep TLS verification enabled. If retry is needed, use a small bounded policy for transient failures of GET requests; respect `Retry-After` when supplied and fail clearly after the limit. Do not retry malformed data or hide partial extraction success. [HTTPX clients](https://www.python-httpx.org/advanced/clients/), [timeouts](https://www.python-httpx.org/advanced/timeouts/).

**Snapshot writes:** write and validate a candidate snapshot before replacing the previous usable one. Resolve file paths from configured/project locations with `pathlib`, not an assumed shell directory. Record extraction ranges, retrieval time, counts, and transformation rules in a small metadata file. An HTTP request must never trigger a snapshot rebuild.

## 8. Configuration, logs, and deployment

- Read the small number of settings, such as the snapshot path, centrally. Ordinary environment access and typed values are sufficient; add a settings library only if configuration actually grows. Business defaults belong in named constants rather than scattered literals.
- Use Python's standard logging with module loggers and appropriate levels. Log extraction summaries, unavailable data, and unexpected failures with useful context. Keep server access logs; do not add a monitoring stack for the pilot. [Python logging HOWTO](https://docs.python.org/3.11/howto/logging.html).
- Keep secrets, environment files, local paths, full upstream payloads, and stack traces out of client-facing responses and unnecessary logs. The frontend should receive only public configuration.
- Keep the prepared snapshot read-only at runtime. Do not add an ORM, migration framework, connection pool, Redis, or a scheduler for the current data flow.
- Serve `/api` and the compiled frontend from one origin. Use the development proxy locally; introduce explicit CORS origins only if the deployment actually separates them.
- Register API and static routes before any SPA fallback. Exclude `/api`, API documentation, and missing asset paths from fallback HTML. Verify correct content types, unknown API `404`s, and browser refresh behavior in the container.
- Use the platform port, avoid development reload/debug mode in deployment, and keep dependency updates intentional. Direct dependency pins are already present; they are not a complete transitive lockfile. Save a resolved dependency snapshot during packaging if reproducible builds require it.

## 9. Frontend conventions

- Keep TypeScript strict checking enabled. Give API responses explicit types and make nullable fields visible in those types. Do not use `any` or type assertions to conceal mismatches. TypeScript annotations alone do not validate JSON at runtime. [TypeScript strict](https://www.typescriptlang.org/tsconfig/strict.html).
- Preserve JSON's `snake_case` in API response types; use `camelCase` for local UI variables. Keep request construction and error parsing in a small API module, with typed functions such as `fetchAnalysis` rather than a generic client framework.
- Prefer React Router's existing client data-loading features for route-owned requests. If a small component-level fetch is clearer, isolate it in a focused hook with cleanup that aborts or ignores obsolete requests. Do not introduce a state/query library just for these few controls.
- Derive display values from current data rather than duplicating them in state. Keep decision inputs and the results they represent consistent, and prevent an older response from overwriting a newer selection. [React Effects guidance](https://react.dev/learn/you-might-not-need-an-effect).
- Use semantic controls with labels and keyboard access. Handle loading, validation errors, unavailable data, partial coverage, and zero matched samples explicitly. Hide outcome-derived charts and metrics in Decision view until reveal.
- The intended build uses React Router SPA mode and `build/client`. Even with `ssr: false`, the root is rendered at build time, so avoid browser-only APIs during initial rendering. Do not remove framework dependencies blindly. This mode change remains implementation work. [React Router SPA guidance](https://reactrouter.com/how-to/spa).

## 10. Focused verification

Use pytest for analysis and small temporary SQLite fixtures, then FastAPI `TestClient` for contract behavior. Use its context manager when exercising lifespan. Keep ordinary tests offline; real Elexon probes belong to explicit ingestion verification. Parameterize boundary cases instead of copying test bodies. [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/), [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html).

Prioritize these behaviors as their implementation steps arrive:

- Cutoff equality, multiple eligible revisions, and rejection of later publications.
- January 31 mapping to February 1; correct local date and UTC cutoff construction.
- Duplicate conflict handling, interval alignment, preserved gaps, and zero matched pairs.
- Hand-calculated positive/negative bias, MAE, RMSE, and monthly aggregation with unequal daily coverage.
- Daily/CSV agreement, explicit nulls, units, publication times, ordering, and coverage counts.
- Invalid inputs yielding `422`; unreadable snapshots yielding `503`; unknown APIs yielding `404`.
- Cutoff changes and stale-request handling in the browser, plus Decision view outcome hiding.

Run the relevant tests and frontend type/build checks as code is added, then a Docker smoke check at packaging. Do not add tests for comments, unchanged boilerplate, trivial getters, or a target coverage percentage. Report checks that actually ran and distinguish local, container, and deployed evidence.

## 11. Before marking an implementation step complete

- Names and units make the domain clear; functions have a focused responsibility.
- HTTP inputs, response shapes, nullability, and expected errors are documented and checked.
- Forecasts cannot leak past the decision cutoff; missing data and coverage remain visible.
- Files, SQLite connections, and HTTP clients have explicit owners and cleanup.
- Important behavior has proportionate tests; relevant checks pass.
- Docs reflect the actual behavior, limitations, and evidence.
- No unrelated features, dependency upgrades, or speculative infrastructure were added.

## 12. Deferred engineering options

PostgreSQL and migrations, scheduled ingestion, distributed caching, background queues, authentication, generated API clients, extensive observability, and more elaborate layering belong in [the advanced approach](03-advanced-approach.md). Adopt one only when a concrete need appears, such as ongoing writes, external API consumers, or measured operational problems.

The next action is to wait for the user's instruction identifying which implementation step to start.
