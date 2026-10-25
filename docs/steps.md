# Project completion steps

## Goal and boundaries

Build a small dashboard that shows which national wind forecast was available at a buying decision and how it compared with actual generation. Follow [the problem statement](01-problem-statement.md) and [the planned approach](02-approach-and-stack.md).

Keep the first version to React, FastAPI, pandas, a prepared SQLite snapshot, Recharts, and one Docker image. Build one dashboard with Decision and Accuracy views. No accounts, live ingestion, custom forecasting model, chatbot, background workers, or additional services.

Advanced ideas stay documented in [the advanced approach](03-advanced-approach.md) and [future scope](05-future-scope.md). They are not prerequisites for completing this project. Record implementation limitations in [tradeoffs](04-tradeoffs.md).

Before implementation, read [the engineering conventions](06-engineering-conventions.md) for naming, API contracts, validation, resource handling, and focused tests. These apply within the existing scope; they do not add implementation steps or authorize starting them. Wait for the user's instruction before starting the relevant step.

## Current starting point

- `frontend/` is configured in SPA mode, displays the agreed scope, and proxies local `/api` requests to FastAPI.
- `backend/` exposes typed readiness, daily analysis, monthly summary, and CSV endpoints using the local snapshot.
- Steps 1-4 are complete. `data/` contains the native wind snapshot and provenance; the API reads it without writes and returns decision-time selections and daily/monthly metrics. Dashboard integration and deployment remain. Step 5 has not started.

The frontend reuses the existing starter and produces `frontend/build/client/`. Serving those files through FastAPI remains part of Step 6; local development currently runs Vite and FastAPI separately.

## Working method and time budget

Complete the steps in order. Each step should leave something small that can be checked before moving on. Keep calculations in Python and presentation in React.

| Step | Budget | Result |
| --- | --- | --- |
| 1. Lock the scope and scaffold | 1 hour | Frontend and backend start locally |
| 2. Verify and prepare source data | 3 hours | Reproducible SQLite snapshot and coverage report |
| 3. Implement selection and metrics | 2 hours | Tested analysis functions |
| 4. Expose the API | 1 hour | Dashboard data and CSV endpoints |
| 5. Build and connect the dashboard | 3 hours | Two working views using real data |
| 6. Package and deploy | 2 hours | Working Docker image and public demo |
| 7. Finish documentation and submission | 2 hours | README, video, and checked links |
| Buffer | 2 hours | Resolve data or deployment issues |
| **Total** | **16 hours** | |

If time becomes tight, simplify styling and avoid additional filters or charts. Preserve forecast correctness, visible missing data, required deliverables, and validation.

## Step 1 - Lock the scope and scaffold

**Status: complete (24 October 2026).** Startup commands and scope assumptions are in [the root README](../README.md). Only the health API and scope page are implemented; controls, data, and analysis remain in later steps.

- Use decision dates 1-31 January 2026 and next-day delivery dates 2 January-1 February 2026. Show this convention in the app and README.
- Use a configurable decision time, defaulting to 09:00 Europe/London. Label it as an illustrative assumption rather than a confirmed market deadline.
- Label the datasets as Great Britain national wind generation. Do not describe national generation as the client's own supply or purchase requirement.
- Keep the existing frontend folder. Add a small FastAPI backend, Python dependencies, and a health endpoint. Configure the frontend for client rendering and local API access through the development proxy.
- Use a simple layout: `backend/` for ingestion, analysis, API, and focused tests; `data/` for the prepared snapshot and extraction metadata; the existing frontend folder for the dashboard.
- Keep the UI to a decision date, cutoff time, two views, charts, summary values, and CSV download.

**Done when:** both development servers start, the health endpoint responds, and the scope assumptions are written down.

Verified locally: frontend type checking and production SPA build passed; Uvicorn and Vite started; direct and proxied health responses returned `200` with `{"status":"ok"}`; OpenAPI described the typed health response; unknown API paths returned JSON `404` directly and through Vite. Frontend HTML and the scope-page module were served successfully. No browser rendering, Elexon data, Docker, or deployed-app acceptance was checked in this step.

## Step 2 - Verify and prepare the historical data

**Status: complete (24 October 2026).** See [the snapshot reference](07-data-snapshot.md) for source evidence, build commands, schema, coverage, and limitations. Native FUELHH half-hours and WINDFOR hourly revisions are preserved. The proposed comparison uses hourly forecasts against complete pairs of actual half-hours; treating a forecast label as the following hour is an explicit assumption.

- Inspect real responses from the two allowed Elexon endpoints before writing the full downloader. Confirm response structure, date-filter meaning, retrieval limits, timestamps, units, interval lengths, and forecast publication history.
- Download FUELHH actuals for the required delivery dates, keeping only `fuelType = WIND`. Download WINDFOR revisions covering those delivery dates and enough earlier publication history for the earliest supported cutoff. Do not assume publication and delivery filters mean the same thing.
- Normalize timestamps to UTC; interpret user decisions in Europe/London. Retain delivery time, publication time for forecasts, and generation in MW.
- Check duplicates, invalid values, missing periods, and source interval differences. Collapse identical duplicates; flag conflicting duplicates for inspection and document their resolution rather than choosing an arbitrary row.
- Verify the interval alignment rule before comparing the sources. If resampling is necessary, use the confirmed interval durations and preserve gaps. Do not fill missing generation with zero.
- Write a repeatable script that builds one read-only SQLite snapshot. Preserve forecast revisions so changing the cutoff does not require another download.
- Save source URLs, extraction time, requested ranges, observed coverage, and any alignment or duplicate rules alongside the snapshot. A short metadata file is enough.

**Done when:** the script produces a usable snapshot and a small report showing date coverage, missing records, duplicates, and interval handling. If publication history is unavailable or intervals cannot be aligned reliably, resolve or document that limitation before building the analysis around it.

Verified: live extraction, offline rebuild, SQLite integrity/read-only access, matching embedded/sidecar provenance, and 23 focused tests. The snapshot has all 1,488 actual half-hours and 17,864 forecast revision rows covering 744 hours. All 31 decisions have 24/24 next-day forecast hours at 09:00; midnight has 22/24. Later actual corrections outside the fetched publication window are not guaranteed. Step 3 selection, hourly actual values, and metrics are not implemented.

## Step 3 - Implement forecast selection and calculations

**Status: complete (24 October 2026).** See [the analysis reference](08-analysis-calculations.md) for functions, coverage definitions, a real source-to-error trace, results, and limitations. The calculation layer is independent of FastAPI and uses read-only snapshot loading.

- Convert the selected decision date and cutoff into one timezone-aware timestamp, then identify the following delivery day.
- For each delivery interval, select the forecast with the latest `publishTime` at or before the cutoff. Leave intervals without an eligible forecast missing.
- Match selected forecasts to actual generation using the verified delivery-interval alignment rule.
- Calculate `error = forecast - actual`, MAE, bias, and RMSE using matched pairs only. Return no metric value when there are no matched pairs.
- Return expected, forecast-available, actual-available, and matched interval counts. Use 24 hourly comparison periods per January delivery day under the documented convention, and report native actual coverage separately against 48 half-hours. Require both actual half-hours before calculating an hourly mean.
- Identify the largest positive errors as overforecast periods. Keep monthly results explicitly retrospective: repeat each January decision using its own cutoff, then aggregate matched periods.
- Add focused pytest cases for cutoff equality, rejection of later revisions, latest eligible revision selection, missing pairs, duplicate handling, next-day/month-boundary mapping, and hand-calculated metrics.

**Done when:** the focused tests pass and one real decision day can be traced from source records to selected forecasts and calculated errors.

Verified: 50 snapshot/analysis tests passed, including both real monthly cutoff runs. An independent SQL/Decimal check matched all 24 delivery hours and metrics for the 15 January decision, without changing the snapshot. Default 09:00 analysis has 744/744 matched monthly hours; midnight has 682/744. Selection, coverage, metrics, and top positive errors are implemented as Python results. HTTP analysis endpoints remain in Step 4.

## Step 4 - Expose a small API

**Status: complete (25 October 2026).** See [the API reference](09-api-reference.md) for routes, schemas, inputs, source details, CSV, configuration, and failure behavior. Analysis routes reuse Step 3 and never call Elexon. Health now checks snapshot readability and required provenance.

- Add one analysis endpoint taking a January decision date and cutoff time. Return delivery intervals, forecast publication times, forecast/actual values, errors, metrics, coverage, and source metadata.
- Add a monthly summary endpoint using the same selection functions and cutoff, plus a CSV download for the selected day's analysis. Keep the CSV consistent with the displayed results.
- Validate inputs and clearly distinguish an invalid request, unavailable data, and a server failure.
- Read the packaged snapshot locally; do not call Elexon on every dashboard request. Avoid extra repositories, service layers, or caching infrastructure unless an actual need appears.

**Done when:** representative API requests return results consistent with Step 3, invalid inputs are rejected, and the exported CSV agrees with the response.

Verified: 97 tests passed; direct and Vite-proxied live HTTP checks passed for readiness, daily JSON/CSV at two cutoffs, monthly summary, validation errors, and unknown API paths. JSON/CSV agree, real results match Step 3, and the snapshot checksum is unchanged. Invalid requests return `422`, snapshot failures `503`, and unexpected bugs `500`. Dashboard workflows, Docker, and deployment remain for later steps.

## Step 5 - Build the dashboard and connect real data

- Replace the welcome screen with a single dashboard using the existing styling setup and Recharts.
- Add the January decision-date picker and cutoff control. Display the resulting delivery date and timezone clearly.
- In **Decision view**, show the selected forecast curve and its coverage. Hide actuals and outcome-derived metrics until the user explicitly reveals them or switches to Accuracy view.
- In **Accuracy view**, show forecast versus actual generation, MAE, bias, RMSE, matched coverage, and the largest overforecast periods. Label units as MW and explain the error sign.
- Include a compact retrospective monthly summary using the chosen cutoff; avoid adding a separate analytics section with more filters.
- Show forecast publication times in tooltips, leave chart gaps visible, and explain missing or unavailable values. Add the CSV download and source/extraction details.
- Handle loading, failed requests, and empty results honestly. Check that changing controls updates all displayed results consistently, including when requests finish out of order.
- Check a desktop and a narrow mobile screen. Keep labels readable and controls usable; avoid adding a component framework for this small page.

**Done when:** both workflows use real API data, changing the cutoff changes forecast selection correctly, and the decision screen does not reveal outcomes prematurely.

## Step 6 - Package, verify, and deploy

- Create one multi-stage Docker build: compile the frontend, then package its static files, Python backend, and snapshot into one runtime image. Replace or adapt the starter Docker setup to this arrangement.
- Serve the frontend and API from FastAPI under the same origin. Ensure static routing does not swallow API errors and the server uses the platform-provided port.
- Run the focused Python tests, frontend type check, and frontend production build. Build and start the container, then verify the health endpoint, dashboard, analysis API, static assets, and CSV download.
- Deploy the image to Heroku as planned in the stack document. Verify the current container deployment requirements when implementing this step and record the exact working commands. Keep the snapshot bundled; do not depend on persistent local writes.
- Open the deployed app independently and exercise both views, cutoff changes, and export. Record any unverified behavior plainly.

**Done when:** the public deployment serves real snapshot data and both workflows work from the Docker image. Local success alone does not complete this step.

## Step 7 - Document, demonstrate, and submit

- Write a root README covering the problem, folder layout, prerequisites, local startup, snapshot generation, tests, Docker commands, deployed URL, assumptions, data provenance, limitations, and AI assistance used.
- Update the existing approach and tradeoff docs to match the completed implementation. Keep deferred features in the advanced and future-scope documents.
- Publish the code in a public GitHub repository with an anonymous name. Check tracked files for credentials and personal details that do not belong in the submission.
- Record an unlisted YouTube demo: up to 5 minutes for the client and up to 5 minutes for the technical reviewer, no more than 10 minutes total. Show the buying-decision workflow first, then explain selection, metrics, data limitations, and startup/deployment.
- Check the repository, deployment, and video links in incognito mode.
- Obtain the actual submission-form URL from the assignment owner and submit the links. The supplied docs contain neither that URL nor a submission deadline; do not invent them.

**Done when:** the required artifacts are accessible, the documentation describes what actually works, and the links have been submitted through the supplied form.

## Completion checklist

- [ ] Only the two allowed national wind datasets are used.
- [ ] Forecasts after each decision cutoff cannot enter the selected forecast curve.
- [ ] Missing intervals remain visible and metrics show matched coverage.
- [ ] Decision and Accuracy views work with the historical snapshot.
- [ ] Focused tests, frontend checks, and Docker smoke checks pass.
- [ ] The public app, anonymous repository, README, and unlisted demo are accessible.
- [ ] Submission links are checked and submitted; remaining limitations are documented.
- [ ] Advanced features remain deferred rather than expanding the pilot.
