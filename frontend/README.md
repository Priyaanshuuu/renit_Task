# Frontend

React Router + TypeScript + Vite, configured as a single-page app. Follow [the root README](../README.md) to run both the frontend and Python backend.

From this directory:

```powershell
npm.cmd ci
npm.cmd run dev
```

The development server runs on port 5173 and proxies `/api` to `http://127.0.0.1:8000`. It fails clearly if port 5173 is already occupied.

```powershell
npm.cmd run typecheck
npm.cmd run build
```

The build output is `build/client/`. `npm.cmd run preview` previews the frontend build locally; it is not a production server. Vercel serves the static build using `vercel.mjs`; the old starter Dockerfile is not used.

## Vercel

Use Root Directory `frontend`, preset Vite, and Node 24.x. Set `BACKEND_ORIGIN` to the backend's stable HTTPS Production origin before deploying. Do not include `/api`. `vercel.mjs` sets `npm ci`, `npm run build`, `build/client`, and a same-origin `/api` proxy. No React Router server adapter or CORS change is needed for this SPA. Changing the variable requires redeployment. Local Vite still uses its existing localhost proxy.

Run `npm.cmd run test:deploy-config` to check the origin validation and rewrite configuration. Full instructions, backend setup, access protection, and hosted checks are in [the deployment guide](../docs/11-vercel-deployment.md).

The dashboard uses real `/api/analysis` and `/api/monthly-summary` responses. A route `clientLoader` owns the applied date/time URL, forwards its abort signal to requests, and keeps daily/monthly failures distinct. Decision view excludes outcomes from the chart, table, metrics, monthly summary, and export until explicit reveal. All business calculations stay in Python. See [dashboard behavior and references](../docs/10-dashboard.md).

## Browser checks

Start both servers using the root README, then run:

```powershell
npm.cmd run test:browser
```

The default browser is an installed Chrome, with no Playwright browser download needed. To use installed Edge:

```powershell
$env:PLAYWRIGHT_CHANNEL = "msedge"
npm.cmd run test:browser
```

On a machine without Chrome/Edge, install Playwright Chromium with `npx.cmd playwright install chromium` and set `$env:PLAYWRIGHT_CHANNEL = "chromium"`. Optional `APP_URL` changes the target origin; it must expose the same API. Tests require the bundled snapshot. The runner does not start or stop servers. After installing dependencies, restart Vite if it reports outdated optimized modules.

The checks exercise decision/reveal/accuracy, publication tooltips, actual CSV downloads, cutoff and month boundaries, obsolete requests, unavailable data, null versus zero, and 1440/390/320px layouts. Failure/gap scenarios intercept responses explicitly; they do not change the snapshot. Screenshots and failure traces are in ignored `test-results/`.

`npm.cmd run format` formats the app and browser-check code with Prettier. The interface uses local/system font fallbacks, without an external font request.
