# Project completion steps

## Goal and boundaries

Build a small dashboard that shows which national wind forecast was available at a buying decision and how it compared with actual generation. Follow [the problem statement](01-problem-statement.md) and [the planned approach](02-approach-and-stack.md).

Keep the first version to React, FastAPI, pandas, a prepared SQLite snapshot, Recharts, and one Docker image. Build one dashboard with Decision and Accuracy views. No accounts, live ingestion, custom forecasting model, chatbot, background workers, or additional services.

Advanced ideas stay documented in [the advanced approach](03-advanced-approach.md) and [future scope](05-future-scope.md). They are not prerequisites for completing this project. Record implementation limitations in [tradeoffs](04-tradeoffs.md).

## Current starting point

- `my-react-router-app/` contains a React Router + TypeScript + Vite starter with server rendering enabled and a welcome screen.
- `backend/` has no implementation yet.
- The documentation describes the intended app; the data pipeline, analysis, dashboard, and deployment still need to be built.

Reuse the frontend starter. Configure it as a client-rendered app so FastAPI can serve its compiled files. Avoid running a second production application server or replacing the starter without a concrete need.

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

- Use decision dates 1-31 January 2026 and next-day delivery dates 2 January-1 February 2026. Show this convention in the app and README.
- Use a configurable decision time, defaulting to 09:00 Europe/London. Label it as an illustrative assumption rather than a confirmed market deadline.
- Label the datasets as Great Britain national wind generation. Do not describe national generation as the client's own supply or purchase requirement.
- Keep the existing frontend folder. Add a small FastAPI backend, Python dependencies, and a health endpoint. Configure the frontend for client rendering and local API access through the development proxy.
- Use a simple layout: `backend/` for ingestion, analysis, API, and focused tests; `data/` for the prepared snapshot and extraction metadata; the existing frontend folder for the dashboard.
- Keep the UI to a decision date, cutoff time, two views, charts, summary values, and CSV download.

**Done when:** both development servers start, the health endpoint responds, and the scope assumptions are written down.

## Step 2 - Verify and prepare the historical data

- Inspect real responses from the two allowed Elexon endpoints before writing the full downloader. Confirm response structure, date-filter meaning, retrieval limits, timestamps, units, interval lengths, and forecast publication history.
- Download FUELHH actuals for the required delivery dates, keeping only `fuelType = WIND`. Download WINDFOR revisions covering those delivery dates and enough earlier publication history for the earliest supported cutoff. Do not assume publication and delivery filters mean the same thing.
- Normalize timestamps to UTC; interpret user decisions in Europe/London. Retain delivery time, publication time for forecasts, and generation in MW.
- Check duplicates, invalid values, missing periods, and source interval differences. Collapse identical duplicates; flag conflicting duplicates for inspection and document their resolution rather than choosing an arbitrary row.
- Verify the interval alignment rule before comparing the sources. If resampling is necessary, use the confirmed interval durations and preserve gaps. Do not fill missing generation with zero.
- Write a repeatable script that builds one read-only SQLite snapshot. Preserve forecast revisions so changing the cutoff does not require another download.
- Save source URLs, extraction time, requested ranges, observed coverage, and any alignment or duplicate rules alongside the snapshot. A short metadata file is enough.

**Done when:** the script produces a usable snapshot and a small report showing date coverage, missing records, duplicates, and interval handling. If publication history is unavailable or intervals cannot be aligned reliably, resolve or document that limitation before building the analysis around it.

## Step 3 - Implement forecast selection and calculations

- Convert the selected decision date and cutoff into one timezone-aware timestamp, then identify the following delivery day.
- For each delivery interval, select the forecast with the latest `publishTime` at or before the cutoff. Leave intervals without an eligible forecast missing.
- Match selected forecasts to actual generation using the verified delivery-interval alignment rule.
- Calculate `error = forecast - actual`, MAE, bias, and RMSE using matched pairs only. Return no metric value when there are no matched pairs.
- Return expected, forecast-available, actual-available, and matched interval counts. Explain the basis of the expected count; January dates normally have 48 half-hour intervals if that is the verified comparison interval.
- Identify the largest positive errors as overforecast periods. Keep monthly results explicitly retrospective: repeat each January decision using its own cutoff, then aggregate matched periods.
- Add focused pytest cases for cutoff equality, rejection of later revisions, latest eligible revision selection, missing pairs, duplicate handling, next-day/month-boundary mapping, and hand-calculated metrics.

**Done when:** the focused tests pass and one real decision day can be traced from source records to selected forecasts and calculated errors.

## Step 4 - Expose a small API

- Add one analysis endpoint taking a January decision date and cutoff time. Return delivery intervals, forecast publication times, forecast/actual values, errors, metrics, coverage, and source metadata.
- Add a monthly summary endpoint using the same selection functions and cutoff, plus a CSV download for the selected day's analysis. Keep the CSV consistent with the displayed results.
- Validate inputs and clearly distinguish an invalid request, unavailable data, and a server failure.
- Read the packaged snapshot locally; do not call Elexon on every dashboard request. Avoid extra repositories, service layers, or caching infrastructure unless an actual need appears.

**Done when:** representative API requests return results consistent with Step 3, invalid inputs are rejected, and the exported CSV agrees with the response.

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
