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

The build output is `build/client/`. `npm.cmd run preview` previews the frontend build locally; it is not a production server. The starter Dockerfile still assumes a Node server build and will be replaced/adapted during Step 6, when FastAPI will serve the compiled frontend.

Step 1 displays the project scope only. The dashboard and data requests will be implemented in later steps.
