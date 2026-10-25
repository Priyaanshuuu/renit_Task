# My engineering conventions

I used these conventions to keep the pilot readable and reliable without adding unnecessary layers. I reviewed the linked official references during implementation on 24-25 October 2026. These notes describe my choices and maintenance rules; they are not a claim of production certification.

## Scope and dependencies

I use Python 3.12 for Vercel parity and retain compatibility with the existing Python 3.11 local environment. Root `requirements.txt` contains the API runtime pins; `backend/requirements.txt` includes those plus development, download, and test tools. The frontend uses strict TypeScript and the existing React Router SPA setup.

I keep dependency updates intentional and check documentation against the installed version. Direct Python pins are not a complete transitive lockfile. The npm lockfile records the resolved frontend dependencies.

## Naming and code style

| Area | My convention | Example |
| --- | --- | --- |
| Python modules, functions, variables | `snake_case` | `analyze_day`, `cutoff_time` |
| Python classes | `PascalCase` | `GenerationRecord`, `AnalysisResponse` |
| JSON fields and SQL names | `snake_case` | `forecast_mw`, `wind_forecasts` |
| React components and TypeScript types | `PascalCase` | `GenerationChart`, `Analysis` |
| TypeScript variables and functions | `camelCase` | `decisionDate`, `fetchAnalysis` |
| API paths | Lowercase resources, hyphens for multiple words | `/api/monthly-summary` |
| Tests | Observable behavior | `test_excludes_forecasts_after_cutoff` |

My Python naming follows [PEP 8](https://peps.python.org/pep-0008/#naming-conventions). I keep framework filenames such as `root.tsx` and `routes.ts`.

I include domain and units in names: `forecast_mw`, `actual_mw`, `error_mw`, `delivery_start`, and `published_at`. A calendar `decision_date` is distinct from the instant `decision_cutoff_at`. Elexon's source field names are mapped at ingestion rather than mixed throughout the app.

I prefer ordinary typed functions, early returns, and small helpers with a clear responsibility. Comments explain assumptions and non-obvious rules. I avoid generic manager classes, wildcard imports, vague utility modules, and type suppressions that conceal mismatches.

## Module ownership

| Module | Responsibility |
| --- | --- |
| `backend/app/main.py` | FastAPI app creation and router registration |
| `backend/app/routes.py` | HTTP handlers, error translation, provenance summary, CSV |
| `backend/app/schemas.py` | Query and response contracts |
| `backend/app/analysis.py` | Windows, selection, alignment, coverage, and metrics |
| `backend/app/storage.py` | Read-only SQLite access and connection ownership |
| `backend/app/snapshot.py` | Native-record validation and snapshot construction |
| `backend/scripts/build_snapshot.py` | Explicit download and preparation command |
| `frontend/app/routes/home.tsx` | Applied selection, data loading, and dashboard presentation |
| `frontend/app/lib/api.ts` | API response types, shape checks, requests, and failure messages |

Routes depend on storage and analysis. Analysis does not import FastAPI or perform file/network access. Downloads happen only through preparation commands. One `APIRouter` and ordinary modules are enough for this pilot; [FastAPI's router guidance](https://fastapi.tiangolo.com/tutorial/bigger-applications/) supports that arrangement.

## HTTP contracts

I use read-only `GET` endpoints with query parameters and direct response objects. [The API reference](09-api-reference.md) is the detailed contract.

- Daily JSON and CSV share the same query model. Dates are limited to January 2026; cutoffs use exact local `HH:MM`. Unknown fields are rejected.
- Pydantic response models make groups, units, timestamps, and nullability explicit. I use UTC ISO timestamps with `Z` and return the effective cutoff and decision timezone.
- Missing values are JSON `null`; zero remains valid. The API retains numeric precision, and React rounds only for display.
- CSV reuses the daily analysis, uses explicit headers and an attachment filename, and represents missing values with empty cells.
- Partial coverage is a valid `200` response with counts and nulls. Invalid queries return `422`, unknown routes `404`, unavailable snapshot/provenance `503`, and unexpected bugs `500`.
- Expected HTTP failures use FastAPI's normal `detail` structure. Client messages do not expose server tracebacks or filesystem details. The frontend also handles non-JSON failure responses safely.

These choices follow [query models](https://fastapi.tiangolo.com/tutorial/query-param-models/), [response models](https://fastapi.tiangolo.com/tutorial/response-model/), [error handling](https://fastapi.tiangolo.com/tutorial/handling-errors/), and [HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html#name-status-codes). I apply strictness where it prevents hidden coercion while still allowing valid URL date/time parsing; see [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/).

## Time and calculation rules

I interpret decisions with `ZoneInfo("Europe/London")` and convert them to UTC. Next-day delivery uses a half-open local calendar range. January has 24 comparison hours and 48 actual half-hours per delivery day; an extension across daylight-saving changes would need calendar-derived counts.

Forecast publications are filtered with `published_at <= decision_cutoff_at` before revision selection. Conflicting duplicate keys fail explicitly. Actuals use the latest revision within the snapshot, with both half-hours required for each hourly mean.

I preserve gaps, exclude unmatched pairs from every metric, and pool matched hourly errors for monthly results. Metrics are unavailable when there are no matches. Generation stays in MW; I do not sum power values as though they were energy. The interval assumption and publication-window limits are in [the source reference](07-data-snapshot.md).

I keep these rules in one Python implementation shared by JSON, monthly analysis, and CSV. React only formats results. Python's [datetime](https://docs.python.org/3.11/library/datetime.html#aware-and-naive-objects) and [zoneinfo](https://docs.python.org/3.11/library/zoneinfo.html) references explain the time representation.

## Resource ownership and execution

I open SQLite with `mode=ro`, parameterize queries, and create, use, and close each connection inside the same synchronous call. A connection context manager alone does not close the connection; I use explicit cleanup. [SQLite reference](https://docs.python.org/3.11/library/sqlite3.html).

Local reads and calculations use synchronous FastAPI handlers, which run outside its async event loop. I reserve `async def` for awaitable I/O. If shared lifecycle resources are introduced, I would use `lifespan` with explicit cleanup. [Concurrency](https://fastapi.tiangolo.com/async/), [lifespan](https://fastapi.tiangolo.com/advanced/events/).

The downloader owns a context-managed HTTPX client, keeps timeouts and TLS verification enabled, checks response statuses, and uses bounded retries for selected transient GET failures. Invalid data fails explicitly. The snapshot builder validates a candidate before replacing the previous artifact. [HTTPX clients](https://www.python-httpx.org/advanced/clients/), [timeouts](https://www.python-httpx.org/advanced/timeouts/).

## Frontend state and accessibility

I preserve the API's `snake_case` fields in response types and use `camelCase` for local UI names. Runtime shape checks supplement TypeScript; types alone do not validate JSON.

React Router's client loader owns applied query parameters and forwards cancellation signals. I derive display values from the current response, remove stale results during loading, and hide outcomes until explicit reveal. This is a presentation workflow, not access control: the API response contains actuals.

Controls have labels and keyboard focus styles. Loading, errors, partial coverage, and unavailable metrics have explicit states. Charts preserve null gaps and have an hourly table alternative. The root loading fallback is safe for build-time rendering in [SPA mode](https://reactrouter.com/how-to/spa).

## Configuration and hosting

I keep configuration small and resolve snapshot paths from the project location. Logging uses Python's standard library, with diagnostics on the server and short failure messages in the client.

Vite proxies `/api` locally. In production, `frontend/vercel.json` forwards it to the separately deployed API, so browser requests stay on the frontend origin without CORS middleware. API failures and missing assets are not routed to dashboard HTML. [Deployment notes](11-vercel-deployment.md).

Secrets, environment files, local paths, and raw upstream payloads do not belong in public responses or unnecessary logs. Runtime access does not rebuild the snapshot or require persistent writes.

## Verification and maintenance

I focus tests on cutoff boundaries, revision selection, duplicates, gaps, zero values, hand-calculated metrics, monthly pooling, date boundaries, JSON/CSV agreement, and expected HTTP failures. Browser checks cover reveal behavior, applied selections, cancellation, errors, and narrow layouts. Synthetic fixtures and intercepted responses are identified as such.

My normal checks are pytest, frontend type checking, the production build, and the focused browser/configuration suites. I record what passed locally separately from public deployment checks. Test patterns follow [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/) and [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html).

For future changes, I check naming, units, contracts, resource cleanup, important failure paths, and documentation before considering the work complete. Additional databases, workers, caches, generated clients, and service layers remain [deferred options](03-advanced-approach.md) until a concrete need justifies them.
