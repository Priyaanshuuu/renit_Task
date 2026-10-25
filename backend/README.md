# Backend setup

I use Python 3.12 for parity with Vercel. The existing Python 3.11 environment remains usable locally. The local virtual environment lives in `backend/.venv` and is excluded from Git.

From the repository root in PowerShell:

```powershell
python -m venv backend/.venv
& ./backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
```

If `python` is unavailable, replace it in the first command with the full path to your Python executable. The environment's Python can be called directly, so activation is optional and PowerShell execution-policy changes are unnecessary.

To activate it in a shell that permits PowerShell scripts:

```powershell
./backend/.venv/Scripts/Activate.ps1
```

## Installed packages

| Package | Purpose |
| --- | --- |
| FastAPI | Backend API and request validation |
| Uvicorn | Run the API server |
| pandas | Available for local tabular inspection; current analysis uses the standard library |
| HTTPX | Download Elexon data and support API checks |
| tzdata | Europe/London timezone support on Windows |
| pytest | Focused analysis and API tests |

SQLite is included in Python through `sqlite3`; no separate database package or server is needed.

Check the environment:

```powershell
& ./backend/.venv/Scripts/python.exe -m pip check
& ./backend/.venv/Scripts/python.exe -c "import fastapi, uvicorn, pandas, httpx, pytest, sqlite3; from zoneinfo import ZoneInfo; print(ZoneInfo('Europe/London')); print('Backend dependencies ready')"
```

## Run the API

From the repository root:

```powershell
& ./backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

`GET http://127.0.0.1:8000/api/health` returns `{"status":"ok","snapshot_ready":true}` when the snapshot and required provenance can be read; otherwise it returns `503`. This does not promise complete observation coverage. OpenAPI documentation is at `http://127.0.0.1:8000/docs`.

The API provides daily analysis, compact retrospective monthly summaries, and CSV export alongside readiness. See [the API reference](../docs/09-api-reference.md) for inputs, outputs, configuration, and errors. I keep snapshot preparation outside API startup:

```powershell
& ./backend/.venv/Scripts/python.exe -m backend.scripts.build_snapshot
& ./backend/.venv/Scripts/python.exe -m backend.scripts.build_snapshot --offline
& ./backend/.venv/Scripts/python.exe -m pytest backend/tests -q
```

These commands run from the repository root. Offline rebuilds require the local response cache. See [the snapshot reference](../docs/07-data-snapshot.md) for source evidence, schema, coverage, and limitations.

My calculation layer uses `storage.read_snapshot`, `analysis.analyze_day`, and `analysis.analyze_month` for read-only loading, decision-time forecast selection, hourly alignment, coverage, metrics, and top overforecasts. See [the analysis reference](../docs/08-analysis-calculations.md) for usage and validation. These functions do not make network requests or mutate the snapshot.

I expose those calculations through validated HTTP routes and connect the dashboard to them. Expected data-readiness failures return safe API messages. Runtime reads use the bundled file or `WIND_SNAPSHOT_PATH`, without source downloads or shared database connections.

## Vercel

Deploy from the **repository root**, not this directory, using the FastAPI preset. Root `app.py` exports the existing application; `.python-version` selects Python 3.12. Root `requirements.txt` installs API runtime dependencies only. This directory's requirements include those pins plus local development/download/test tools.

The root includes `data/wind_snapshot.sqlite` at its existing file-relative path. Leave `WIND_SNAPSHOT_PATH` unset. No CORS settings are needed because the separately deployed frontend proxies `/api` requests. See [the deployment guide](../docs/11-vercel-deployment.md) for both projects, public readiness checks, and limits. I deployed the API at `https://renittask.vercel.app`; its public health check returned `200` with snapshot readiness.
