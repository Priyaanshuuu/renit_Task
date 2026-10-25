# My Vercel deployment

I deployed the frontend and backend as separate Vercel projects from the same repository. My backend is at `https://renittask.vercel.app`, and its public `/api/health` endpoint returned `200` with `snapshot_ready: true`. The dashboard works with the static frontend rewrite below. These notes record my settings, local validation, and checks for future deployments.

## 1. Deploy the backend

I use the repository root for the backend project so both the Python app and its sibling data directory are available. These are the settings needed to reproduce that deployment:

| Setting | Value |
| --- | --- |
| Root Directory | Repository root (`.`), **not `backend/`** |
| Framework Preset | FastAPI |
| Python | 3.12, selected by the root `.python-version` |
| Build / Install / Output overrides | Leave unset; use the FastAPI preset |
| Environment variables | None required |

The root `app.py` exports the existing FastAPI app. The root `requirements.txt` contains API runtime dependencies only; pandas, download tools, and pytest are not needed by requests. The root `vercel.json` selects FastAPI, gives the function 30 seconds, and excludes the frontend, documentation, local environment, raw download cache, and tests from the runtime bundle.

The prepared `data/wind_snapshot.sqlite` is tracked and must stay in the repository. The project root includes both `backend/` and `data/`, so the existing file-relative path works without copying the database or changing `WIND_SNAPSHOT_PATH`. Leave that environment variable unset on Vercel. Runtime access remains read-only; no downloads, database server, persistent volume, migrations, or writes are needed. Updating data means rebuilding the snapshot locally and redeploying.

I use the stable Production domain, `https://renittask.vercel.app`, as the frontend destination. For a new deployment, my backend acceptance checklist is:

- `/api/health` returns `{"status":"ok","snapshot_ready":true}`.
- `/api/analysis?decision_date=2026-01-15&cutoff_time=09:00` returns JSON with 24 forecast/matched hours.
- `/api/monthly-summary?cutoff_time=00:00` reports 682 matched hours out of 744.
- `/api/analysis.csv?decision_date=2026-01-15&cutoff_time=09:00` downloads a CSV.
- `/api/does-not-exist` returns JSON `404`; `/docs` opens the API documentation.

The backend root `/` is intentionally not a dashboard and may return `404`. Use `/api/health` to check readiness.

## 2. Deploy the frontend

I use a second project for the static frontend, with these settings:

| Setting | Value |
| --- | --- |
| Root Directory | `frontend` |
| Framework Preset | Vite |
| Node.js | 24.x, also declared in `frontend/package.json` |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `build/client` |
| Environment variables | None required |

`frontend/vercel.json` contains the explicit rule:

```json
{
  "source": "/api/:path*",
  "destination": "https://renittask.vercel.app/api/:path*"
}
```

I replaced the dynamic frontend configuration after Vercel reported a missing rewrite destination. The static `vercel.json` contains the destination directly and is the only Vercel configuration in the frontend root. `BACKEND_ORIGIN` is no longer used. If I change the backend domain, I update this destination and redeploy. I did not reproduce the precise cause of the earlier hosted compilation error locally.

The browser continues requesting `/api` on the frontend origin, including CSV downloads. Vercel forwards those requests to the backend, so CORS middleware is unnecessary. The app currently has one page, `/`, with query-string selections; refreshing a bookmarked selection uses the static `index.html`. There is no blanket HTML fallback to swallow unknown API requests or missing assets. If I add nested client routes later, their fallback will need to stay separate from `/api` and missing assets.

## 3. Check the public dashboard

For future releases, I use this incognito checklist against the frontend Production URL:

1. Load `/` and confirm the forecast appears with outcomes hidden.
2. Apply 15 January at `09:00`, then reveal outcomes. Daily MAE is about 782.8 MW and monthly matched coverage is 744/744.
3. Apply `00:00`; daily forecast coverage becomes 22/24 and monthly matched coverage becomes 682/744. Outcomes should hide again after applying.
4. Select 31 January and verify delivery on 1 February.
5. Reveal outcomes and download CSV. Refresh the URL and check a narrow/mobile viewport.
6. Request `/api/health` and `/api/does-not-exist` through the **frontend** domain. Expect readiness JSON and JSON `404`, respectively. A missing `/assets/does-not-exist.js` should not return dashboard HTML.

For this public demo, the backend Production URL must be reachable without a Vercel login. If the rewrite returns an authentication page, check backend Deployment Protection and use its public Production domain. Preview deployment URLs may be protected. I keep access settings in the Vercel dashboard and do not embed bypass tokens in the project.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Backend is detected as a frontend, or no FastAPI app found | Backend project Root Directory is `.` and preset is FastAPI; root `app.py` and `requirements.txt` are included |
| Backend health returns `503` | Snapshot is tracked, included in the function, and `WIND_SNAPSHOT_PATH` is unset; inspect runtime logs |
| Rewrite is missing `destination` | Deploy the latest commit containing `frontend/vercel.json` and the explicit backend URL; remove the obsolete `vercel.mjs` |
| Dashboard or CSV gets login HTML/401 | Verify backend Production domain in incognito mode and check Deployment Protection |
| API works directly but fails through frontend | Check the static destination URL, redeploy after changes, and inspect proxy/backend logs |
| Frontend build cannot find output | Select Vite and `build/client`; do not use a Node server or `build/server` output |

## Local verification and boundaries

My Windows validation recorded 97 passing backend tests on Python 3.12.14 in an isolated environment containing the root runtime dependencies plus HTTPX/pytest, without pandas or Uvicorn. The existing Python 3.11 environment also passed all 97 tests. Both runs retain the existing Starlette/HTTPX test-client deprecation warning. The root ASGI entrypoint passed readiness, daily/monthly analysis, CSV, and JSON error checks. A separate minimal app/backend/data folder check confirmed the snapshot path works outside the source checkout. The snapshot was unchanged.

Frontend type checking, production SPA build, and two deployment configuration tests passed. These configuration tests run locally and do not emulate Vercel's hosted proxy or bundler.

Normal local development is unchanged: Uvicorn on port 8000 and Vite on 5173 with its existing proxy. Local Vite does not use Vercel's production rewrite. See [the root README](../README.md) for commands.

From `frontend/`, `npm.cmd run test:deploy-config` checks that the static configuration has the explicit HTTPS destination and no conflicting dynamic config. Frontend type checking/build and the focused Python tests check the app. I keep the public backend health check separate from full hosted workflow acceptance. An automated hosted browser run is not recorded here; the checklist above remains the procedure for checking releases.

I chose Vercel's native frontend and Python configurations instead of the earlier Heroku/single-image plan. The original brief still lists Docker: the starter `frontend/Dockerfile` is unused by this deployment and has not been validated as a working project image.

## Official references

I reviewed these references on 25 October 2026:

- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi): app entrypoint, framework detection, and function configuration.
- [Python runtime](https://vercel.com/docs/functions/runtimes/python): supported Python versions, dependency files, and explicit bundle exclusions. The standard Python bundle limit is 500 MB; the snapshot is about 1.4 MiB before dependencies.
- [Programmatic Vercel configuration](https://vercel.com/docs/project-configuration/vercel-ts): build-time configuration, environment variables, and `.mjs` support.
- [External rewrites](https://vercel.com/docs/routing/rewrites): forwarding API traffic while retaining the browser's origin.
- [Deployment Protection](https://vercel.com/docs/deployment-protection): public versus protected deployment access.
