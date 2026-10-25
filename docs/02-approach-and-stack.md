# My approach and stack

I chose a small architecture around one historical snapshot and two dashboard workflows. The snapshot, calculations, API, and dashboard are implemented, and I deployed the frontend and backend on Vercel. [The dashboard reference](10-dashboard.md) and [deployment notes](11-vercel-deployment.md) describe the current setup.

## Dashboard workflows

- **Decision view:** a January decision date and cutoff select the forecast published by that time for next-day delivery. Outcomes stay hidden until reveal.
- **Accuracy view:** the same selected forecast is compared with actual generation, with matched coverage and error metrics.

## Data flow

1. My preparation script downloads the permitted Elexon data and retains forecast revisions.
2. It validates timestamps, units, delivery grids, duplicates, and missing records.
3. It writes a SQLite snapshot with source provenance and coverage.
4. The analysis selects the latest forecast with `published_at <= decision cutoff` for each delivery hour.
5. It compares the forecast with the mean of the two actual half-hours, requiring both.
6. FastAPI returns the results to React and uses the same daily analysis for CSV.

I checked real responses to distinguish publication filtering from delivery filtering. I preserve the native half-hour actuals and hourly forecast revisions. Treating a forecast's hour label as the following hour remains an explicit comparison assumption. See [the source evidence](07-data-snapshot.md) and [calculation rules](08-analysis-calculations.md).

## Stack choices

| Tool | Why I chose it |
| --- | --- |
| React + TypeScript + Vite | A small frontend with strict type checking and an existing SPA setup |
| Recharts | Chart presentation, publication tooltips, and explicit null gaps |
| Python + FastAPI | Typed API contracts, validation, and generated API documentation |
| Python standard library | The bounded analysis fits ordinary date/time, math, and SQLite functions |
| pandas | Available in the development environment for tabular inspection; not required by API requests |
| SQLite | A portable historical snapshot without a database server |
| pytest + Playwright | Focused calculation/API tests and browser workflow checks |
| Vercel, two projects | Static frontend hosting and a separate Python API, connected by a frontend rewrite |

The backend bundles the read-only snapshot from the repository root. The frontend's static `vercel.json` forwards `/api` to `https://renittask.vercel.app/api`. I do not rely on persistent runtime writes. The original brief's Docker deliverable is separate from this hosting choice; its status is recorded in [the deployment notes](11-vercel-deployment.md).

## Results shown in the portal

I show forecast publication times, hourly forecast/actual curves in MW, native and matched coverage, MAE, bias, RMSE, largest positive errors, CSV export, and source limitations. The monthly summary stays explicitly retrospective and appears only after outcomes are revealed.

For matched periods, `error = forecast - actual`:

- **MAE:** average absolute error in MW.
- **Bias:** average signed error; positive means overforecast.
- **RMSE:** square root of mean squared error, giving larger misses more weight.

I exclude unmatched periods and show the sample count. Missing values stay null, and metrics are unavailable with no matched pairs. Monthly metrics pool matched hourly errors instead of averaging daily metrics.

## Engineering boundaries

I keep selection and metrics in one Python implementation, use typed HTTP contracts, and make resource ownership and errors explicit. My checks cover cutoff boundaries, revision selection, missing pairs, calculations, CSV agreement, and next-day mapping. I keep additional infrastructure in [future scope](05-future-scope.md) until there is a concrete need for it. The detailed conventions are in [the engineering reference](06-engineering-conventions.md).
