# Project steps and progress

I built this pilot in small stages so I could check the data and calculations before connecting the dashboard. My goal was one focused portal for reviewing the forecast available at a buying decision and its next-day outcome.

The implementation uses React, FastAPI, a prepared SQLite snapshot, and Recharts. I kept live ingestion, accounts, custom prediction models, and additional services outside the pilot. My implementation choices are in [the approach](02-approach-and-stack.md), [engineering conventions](06-engineering-conventions.md), and [tradeoffs](04-tradeoffs.md).

## Original time budget

I used the brief's 16-hour limit to guide the scope. These are planning estimates, not a measured timesheet.

| Stage | Budget | Result |
| --- | --- | --- |
| 1. Scope and scaffold | 1 hour | Local frontend and backend |
| 2. Source verification and snapshot | 3 hours | Reproducible historical data and provenance |
| 3. Selection and calculations | 2 hours | Tested daily and monthly analysis |
| 4. API | 1 hour | JSON, readiness, and CSV endpoints |
| 5. Dashboard | 3 hours | Decision and Accuracy workflows |
| 6. Deployment | 2 hours | Separate Vercel frontend and backend projects |
| 7. Documentation and submission | 2 hours | Project references and submission artifacts |
| Buffer | 2 hours | Data or deployment issues |
| **Total** | **16 hours** | |

## 1. Scope and scaffold

I fixed the decision range to 1-31 January 2026, with next-day delivery from 2 January to 1 February. I made the cutoff configurable, with an illustrative 09:00 Europe/London default.

I reused the frontend starter in SPA mode, added FastAPI, and configured Vite to proxy local `/api` requests. I kept the scope to Great Britain national wind, which cannot establish a customer's own generation or purchase requirement without their demand and contract data.

The initial type check, production build, server startup, direct/proxied health responses, and API `404` checks passed. Later stages added snapshot readiness and analysis.

## 2. Source verification and snapshot

I checked actual Elexon responses before implementing the downloader. Publication filters and delivery dates are handled separately, and forecast revisions are preserved.

The prepared snapshot contains 1,488 native actual half-hours and 17,864 forecast revision rows across 744 delivery hours. I recorded extraction windows, source attribution, duplicate handling, and coverage in the embedded and sidecar reports.

The extraction, offline rebuild, SQLite integrity/read-only checks, and 23 snapshot tests passed at this stage. See [the snapshot reference](07-data-snapshot.md).

## 3. Forecast selection and calculations

I implemented decision windows, latest eligible forecast selection, complete-pair hourly actuals, matched coverage, MAE, bias, RMSE, and largest positive errors in Python.

Forecast eligibility is checked before revision selection. Missing values remain missing. Monthly results repeat each day's cutoff and pool the matched hourly errors.

The snapshot and analysis suite reached 50 passing tests. An independent SQL/Decimal trace matched all 24 hours and daily metrics for the 15 January decision. Monthly matched coverage is 744/744 at 09:00 and 682/744 at midnight. See [the calculation reference](08-analysis-calculations.md).

## 4. API

I exposed the calculations through typed daily JSON, monthly summary, CSV, and readiness endpoints. Requests read the local snapshot without downloading upstream data or writing to the database.

Input validation, null handling, source provenance, JSON/CSV agreement, and expected failure responses are covered by the 97-test Python suite. Direct and Vite-proxied HTTP checks also passed. See [the API reference](09-api-reference.md).

## 5. Dashboard

I connected the Decision and Accuracy views to the API. Decision view hides outcomes until reveal; changing a selection hides them again. The dashboard includes publication timestamps, visible gaps, matched coverage, daily metrics, overforecasts, a retrospective monthly summary, CSV, and source details.

Type checking, the production SPA build, and six Chrome browser checks passed. The browser checks cover real snapshot workflows, desktop/390px/320px layouts, and controlled failures, delays, and interior gaps. I keep those intercepted scenarios separate from evidence about the real snapshot. See [the dashboard reference](10-dashboard.md).

## 6. Vercel deployment

I deployed the frontend and FastAPI backend as separate Vercel projects. The backend uses the repository root to include the existing snapshot. The frontend serves `build/client` and forwards `/api` through its static `vercel.json` configuration.

I replaced the dynamic frontend configuration after a deployment reported a missing rewrite destination. The explicit destination is now `https://renittask.vercel.app/api/:path*`, and the dashboard works with this setup.

The backend health endpoint returned `200` with snapshot readiness. The Python suite passed on Python 3.12.14 and the existing Python 3.11 environment; the root ASGI entrypoint, frontend type/build checks, and two deployment configuration tests also passed. Local tests do not substitute for hosted browser acceptance. See [the deployment notes](11-vercel-deployment.md).

## 7. Documentation and submission

I keep the source evidence, analysis rules, API contracts, deployment settings, limitations, and AI-assistance disclosure in this repository.

The remaining submission artifacts need their own completion check:

- Public repository access and the required anonymous repository name.
- The frontend demo URL and unlisted video link in the README.
- A video with a customer overview of at most 5 minutes and a technical overview of at most 5 minutes, within 10 minutes total.
- Incognito checks for the submitted links and confirmation through the supplied submission form.
- Resolution of the original brief's Docker deliverable. The starter frontend Dockerfile is not used by Vercel and has not been validated as a working project image.

I have not recorded a submission-form URL, submission confirmation, or completed Docker check here. Advanced work remains in [the advanced approach](03-advanced-approach.md) and [future scope](05-future-scope.md).
