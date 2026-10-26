# Wind forecast analysis

I built this pilot to compare the Great Britain national wind forecast available at a buying decision with actual next-day generation. It includes a prepared snapshot, Python analysis, an API, and a dashboard with Decision and Accuracy views. I deployed the frontend and backend as separate Vercel projects

## Scope

- Decision dates: 1-31 January 2026.
- Next-day delivery dates: 2 January-1 February 2026, interpreting decisions as purchases for the following local calendar day.
- Configurable cutoff: 09:00 Europe/London by default. This is an illustrative assumption, not a confirmed market deadline.
- Only Elexon FUELHH actuals with `fuelType = WIND` and WINDFOR forecasts, at Great Britain national level.
- Decision view and Accuracy view, with charts, coverage, error metrics, and CSV export.
- National wind generation cannot establish the client's own supply or exact purchase requirement without demand and contract data.

## Local startup

I use Python 3.12 for Vercel parity, Node.js 24, and npm. The existing Python 3.11 environment still supports local development. Commands below run from the repository root in PowerShell. The existing Python environment can be reused; otherwise follow [backend setup](backend/README.md).

Start the backend in one terminal:

```powershell
& ./backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Start the frontend in another terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:5173`. Vite forwards `/api` requests to `http://127.0.0.1:8000`, with no browser CORS configuration needed.

The dashboard starts at the 1 January decision and 09:00 cutoff. Choose a date/time and apply it; the resulting URL can be bookmarked. Decision view shows the eligible next-day forecast only. Select **Reveal outcomes** or **Accuracy view** to see actuals, metrics, overforecasts, the retrospective month at that cutoff, and CSV export (which includes outcomes). Applying another selection hides outcomes again. Expand hourly data for publication timestamps and gaps, or source details for extraction information and limitations. See [the dashboard reference](docs/10-dashboard.md).

Interactive API documentation is at `http://127.0.0.1:8000/docs`. Implemented `GET` endpoints:

| Path | Purpose |
| --- | --- |
| `/api/health` | API and snapshot readiness: `{"status":"ok","snapshot_ready":true}` |
| `/api/analysis?decision_date=2026-01-15&cutoff_time=09:00` | Daily selected forecasts, actuals, coverage, metrics, and provenance |
| `/api/monthly-summary?cutoff_time=09:00` | Retrospective January summary |
| `/api/analysis.csv?decision_date=2026-01-15&cutoff_time=09:00` | The same daily interval results as a CSV attachment |

Dates must be in January 2026 and use `YYYY-MM-DD`; cutoffs must use exact `HH:MM`. Invalid/unknown inputs return `422`, unavailable snapshot data returns `503`, and valid partial data returns explicit gaps/counts. The API never downloads data during requests. See [the API reference](docs/09-api-reference.md) for response groups, source windows, configuration, and CSV columns. Optional `WIND_SNAPSHOT_PATH` selects another local snapshot; relative paths resolve from the project root.

Stop each server with Ctrl+C.

## Project layout

- `backend/app/`: FastAPI scaffold, snapshot validation, read-only storage, and pure analysis functions.
- `requirements.txt`: API runtime dependency pins; `backend/requirements.txt` adds local development, download, and test tools.
- `frontend/`: React Router, TypeScript, Vite, and Tailwind frontend.
- `docs/`: requirements, implementation steps, conventions, and deferred approaches.
- `data/`: bundled SQLite wind snapshot and coverage/provenance report; local raw response cache is ignored by Git.

## Prepare the snapshot

From the repository root:

```powershell
& ./backend/.venv/Scripts/python.exe -m backend.scripts.build_snapshot
# Rebuild without downloads after the local response cache exists:
& ./backend/.venv/Scripts/python.exe -m backend.scripts.build_snapshot --offline
```

The snapshot contains 1,488 actual half-hours and 17,864 hourly forecast revision records for the required delivery dates. Forecasts cover all 24 next-day hours at the default 09:00 cutoff; midnight has 22/24. The comparison uses the mean of both actual half-hours for each forecast hour, without gap filling. This assumes each forecast label represents the following hour. See [source evidence, extraction windows, commands, and limitations](docs/07-data-snapshot.md). Actual corrections published after the fetched window are not guaranteed to be included.

Contains BMRS data © Elexon Limited copyright and database right 2026. Source: Elexon Insights Solution / National Energy System Operator.

## Run the Python analysis

From the repository root:

```powershell
& ./backend/.venv/Scripts/python.exe -c "from datetime import date; from backend.app.storage import read_snapshot; from backend.app.analysis import analyze_day; data=read_snapshot(); result=analyze_day(date(2026,1,15),data.actuals,data.forecasts); print(result.coverage); print(result.metrics)"
```

`analyze_day` selects only forecasts available at the chosen cutoff. `analyze_month` repeats each January decision separately and pools matched errors for retrospective metrics. Both preserve gaps, counts, and selected publication times. See [function behavior, validation, and the real-data trace](docs/08-analysis-calculations.md). The API exposes them to the dashboard; React only formats the results.

## Checks and build

```powershell
& ./backend/.venv/Scripts/python.exe -m pip check
& ./backend/.venv/Scripts/python.exe -m pytest backend/tests -q
cd frontend
npm.cmd run typecheck
npm.cmd run build
```

With both development servers running and Chrome installed, run the focused browser checks from `frontend/`:

```powershell
npm.cmd run test:browser
```

Use `$env:PLAYWRIGHT_CHANNEL = "msedge"` for an installed Edge instead. Browser checks cover real snapshot workflows, CSV, and narrow layouts; delayed responses, API failures, and interior gaps use explicit test interception. Screenshots/traces are local ignored artifacts. See [frontend instructions](frontend/README.md).

The frontend uses React Router SPA mode and produces `frontend/build/client/`. Vercel serves this static build separately from the FastAPI backend.

## Deploy on Vercel

Follow [the Vercel deployment guide](docs/11-vercel-deployment.md) for exact settings, checks, and troubleshooting. Import this repository as two projects:

| Project | Root Directory | Framework | Required setting |
| --- | --- | --- | --- |
| Backend (deploy first) | `.` (repository root) | FastAPI | Python 3.12 selected by `.python-version`; no environment variables required |
| Frontend | `frontend` | Vite | API destination is configured in `frontend/vercel.json`: `https://renittask.vercel.app` |

The frontend config builds with `npm run build`, serves `build/client`, and proxies `/api` to the backend. The backend bundles the read-only snapshot. No CORS configuration, database hosting, ingestion job, or frontend environment variable is needed. If the backend domain changes, update the destination in `frontend/vercel.json` and redeploy the frontend. Run `npm.cmd run test:deploy-config` from `frontend/` to check configuration locally. My backend is available at [renittask.vercel.app](https://renittask.vercel.app/api/health), where the health check returned `200` with snapshot readiness. The dashboard is working with the static frontend rewrite; the local test evidence and hosted-check procedure are documented separately.

## Implementation references

I recorded the implementation progress in [the project steps](docs/steps.md) and my naming, API, error-handling, and testing choices in [the engineering conventions](docs/06-engineering-conventions.md).

I used the official [FastAPI first steps](https://fastapi.tiangolo.com/tutorial/first-steps/), [React Router SPA mode](https://reactrouter.com/how-to/spa), and [Vite development proxy](https://vite.dev/config/server-options.html#server-proxy) guidance as implementation references.

## Delivery status and AI assistance

I used AI assistance to review requirements and official references, document engineering choices, implement the snapshot, analysis, API, and dashboard, and write and run focused checks. The source evidence, tests, and limitations are included in this repository.

I have deployed the application on Vercel. I have not added the frontend demo URL, an unlisted video link, or submission confirmation to this README. The original brief also lists Docker; the starter frontend Dockerfile is unused by Vercel and has not been validated as a working project image.
