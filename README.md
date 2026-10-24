# Wind forecast analysis

A pilot for comparing Great Britain national wind forecasts available at a buying decision with actual next-day generation. Step 1 provides a React frontend and FastAPI scaffold; data preparation and analysis are not implemented yet.

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

- `backend/app/`: FastAPI entry point, routes, and response schemas.
- `backend/requirements.txt`: pinned direct Python dependencies.
- `frontend/`: React Router, TypeScript, Vite, and Tailwind frontend.
- `docs/`: requirements, implementation steps, conventions, and deferred approaches.
- `data/`: planned location for the SQLite snapshot and provenance; added during data preparation.

## Checks and build

```powershell
& ./backend/.venv/Scripts/python.exe -m pip check
cd frontend
npm.cmd run typecheck
npm.cmd run build
```

The frontend uses React Router SPA mode and produces `frontend/build/client/`. Serving that build through FastAPI, Docker packaging, and public deployment belong to Step 6. The starter frontend Dockerfile has not yet been adapted to this architecture.

## Implementation references

Read [the project steps](docs/steps.md) and [engineering conventions](docs/06-engineering-conventions.md) before making changes. Each next step requires the user's instruction.

The scaffold follows the official [FastAPI first steps](https://fastapi.tiangolo.com/tutorial/first-steps/), [React Router SPA mode](https://reactrouter.com/how-to/spa), and [Vite development proxy](https://vite.dev/config/server-options.html#server-proxy) guidance.

## Delivery status and AI assistance

There is no deployed URL or demo video yet. AI assistance was used to review the project requirements, document conventions, set up dependencies, and implement the initial scaffold. This README will be updated as implementation and validation progress.
