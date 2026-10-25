# Wind forecast analysis

A pilot for comparing Great Britain national wind forecasts available at a buying decision with actual next-day generation. Steps 1-3 provide the React/FastAPI scaffold, validated historical snapshot, and Python forecast selection and daily/monthly calculations. Analysis HTTP endpoints and dashboard integration are not implemented yet.

## Scope

- Decision dates: 1-31 January 2026.
- Next-day delivery dates: 2 January-1 February 2026, interpreting decisions as purchases for the following local calendar day.
- Planned configurable cutoff: 09:00 Europe/London by default. This is an illustrative assumption, not a confirmed market deadline.
- Only Elexon FUELHH actuals with `fuelType = WIND` and WINDFOR forecasts, at Great Britain national level.
- Planned workflows: Decision view and Accuracy view, with charts, coverage, error metrics, and CSV export.
- National wind generation cannot establish the client's own supply or exact purchase requirement without demand and contract data.

## Local startup

Prerequisites: Python 3.11, Node.js 24, and npm. Commands below run from the repository root in PowerShell. The existing Python environment can be reused; otherwise follow [backend setup](backend/README.md).

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

Open `http://localhost:5173`. Vite forwards `/api` requests to `http://127.0.0.1:8000`, with no browser CORS configuration needed. The frontend page documents the scope; it does not yet show analysis data.

The only implemented API endpoint is `GET /api/health`, returning `{"status":"ok"}`. It checks API process health, not snapshot availability or analysis readiness. Interactive API documentation is at `http://127.0.0.1:8000/docs`.

Stop each server with Ctrl+C.

## Project layout

- `backend/app/`: FastAPI scaffold, snapshot validation, read-only storage, and pure analysis functions.
- `backend/requirements.txt`: pinned direct Python dependencies.
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

`analyze_day` selects only forecasts available at the chosen cutoff. `analyze_month` repeats each January decision separately and pools matched errors for retrospective metrics. Both preserve gaps, counts, and selected publication times. See [function behavior, validation, and the real-data trace](docs/08-analysis-calculations.md). They are not yet connected to the API or dashboard.

## Checks and build

```powershell
& ./backend/.venv/Scripts/python.exe -m pip check
& ./backend/.venv/Scripts/python.exe -m pytest backend/tests -q
cd frontend
npm.cmd run typecheck
npm.cmd run build
```

The frontend uses React Router SPA mode and produces `frontend/build/client/`. Serving that build through FastAPI, Docker packaging, and public deployment belong to Step 6. The starter frontend Dockerfile has not yet been adapted to this architecture.

## Implementation references

Read [the project steps](docs/steps.md) and [engineering conventions](docs/06-engineering-conventions.md) before making changes. Each next step requires the user's instruction.

The scaffold follows the official [FastAPI first steps](https://fastapi.tiangolo.com/tutorial/first-steps/), [React Router SPA mode](https://reactrouter.com/how-to/spa), and [Vite development proxy](https://vite.dev/config/server-options.html#server-proxy) guidance.

## Delivery status and AI assistance

There is no deployed URL or demo video yet. AI assistance was used to review requirements and official references, document conventions, set up dependencies, implement the scaffold and snapshot preparation, and write/run focused checks. This README will be updated as implementation and validation progress.
