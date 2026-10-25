# Backend setup

Use Python 3.11. The local virtual environment lives in `backend/.venv` and is excluded from Git.

From the repository root in PowerShell:

```powershell
python -m venv backend/.venv
& ./backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
```

If `python` is unavailable, replace it in the first command with the full path to your Python 3.11 executable. The environment's Python can be called directly, so activation is optional and PowerShell execution-policy changes are unnecessary.

To activate it in a shell that permits PowerShell scripts:

```powershell
./backend/.venv/Scripts/Activate.ps1
```

## Installed packages

| Package | Purpose |
| --- | --- |
| FastAPI | Backend API and request validation |
| Uvicorn | Run the API server |
| pandas | Prepare and compare historical wind data |
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

`GET http://127.0.0.1:8000/api/health` returns `{"status":"ok"}` for API process health only. It does not check data readiness. OpenAPI documentation is at `http://127.0.0.1:8000/docs`.

The API currently has only the health route and its response schema. Step 2 added explicit snapshot preparation outside API startup:

```powershell
& ./backend/.venv/Scripts/python.exe -m backend.scripts.build_snapshot
& ./backend/.venv/Scripts/python.exe -m backend.scripts.build_snapshot --offline
& ./backend/.venv/Scripts/python.exe -m pytest backend/tests -q
```

These commands run from the repository root. Offline rebuilds require the local response cache. See [the snapshot reference](../docs/07-data-snapshot.md) for source evidence, schema, coverage, and limitations.

Step 3 added `storage.read_snapshot`, `analysis.analyze_day`, and `analysis.analyze_month`: read-only loading, decision-time forecast selection, hourly alignment, coverage, metrics, and top overforecasts. See [the analysis reference](../docs/08-analysis-calculations.md) for usage and validation. These functions do not make network requests or mutate the snapshot.

Analysis HTTP endpoints, data readiness checks, and connecting the functions to the API remain in Step 4. Follow [the project steps](../docs/steps.md) and [engineering conventions](../docs/06-engineering-conventions.md) when that step is authorized.
