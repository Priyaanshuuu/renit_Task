# Approach and stack

Status: the scaffold, snapshot, calculations, and analysis HTTP API are implemented (Steps 1-4). Dashboard integration and deployment remain planned. Update this document as those steps are completed.

Use [the engineering conventions](06-engineering-conventions.md) for implementation details such as naming, API contracts, errors, and testing. Keep the architecture below small; clear code and reliable behavior do not require additional services or layers. Follow [the project steps](steps.md) only when the user authorizes the relevant implementation work.

## Simple approach

Build one dashboard with two views:

- **Decision view:** choose a January decision date and cutoff, then see the next day's wind forecast available at that time.
- **Accuracy view:** compare those selected forecasts with actual generation and show the errors.

## Data flow

1. A Python script downloads the required historical Elexon data, including forecast revisions.
2. Validate timestamps, units, interval lengths, duplicates, and missing records.
3. Store the cleaned records in a small SQLite snapshot. Keep source details and the extraction timestamp.
4. For each delivery period, select the latest forecast with `publishTime <= decision cutoff`.
5. Match that forecast with actual generation for the same delivery interval.
6. FastAPI returns the selected data and metrics to React.

Do not assume API date filters refer to delivery time: verify their meaning with real responses. Fetch enough publication history to cover eligible forecasts. If interval lengths differ, verify and document how they are aligned before calculating errors.

Step 2 verified publication-time filtering, half-hour FUELHH actual averages in MW, and hourly WINDFOR forecast labels. The snapshot preserves both native resolutions. The pilot will compare each hourly forecast with the mean of its two actual half-hours, requiring both; interpreting the forecast label as the following hour remains an explicit assumption. See [the source evidence and coverage report](07-data-snapshot.md).

Step 3 implements that comparison and decision-time revision selection, with Python dataclasses for daily/monthly results. Monthly metrics pool matched hourly errors. See [the analysis reference and real-data trace](08-analysis-calculations.md). Step 4 exposes these results as validated daily JSON, compact monthly summaries, and CSV; see [the API reference](09-api-reference.md).

## Stack and why

| Tool | Why it fits |
| --- | --- |
| React + TypeScript + Vite | A straightforward frontend with useful type checking. |
| Recharts | Readable charts without building chart components from scratch. |
| Python + FastAPI | Small API, input validation, and generated API documentation. |
| pandas | Available for tabular inspection; the bounded snapshot and current analysis use standard-library functions. |
| SQLite | Enough for a small historical dataset; no database server to manage. |
| pytest | Test the forecast selection and calculations that matter most. |
| Docker + Heroku | Package the frontend build and Python server as one deployable app. |

Serve the compiled React files through FastAPI. Bundle the read-only data snapshot in the image. Do not rely on Heroku's local filesystem for persistent updates.

## What the dashboard shows

- Forecast and actual generation charts, with MW clearly labelled.
- Forecast publication times in tooltips.
- Hourly comparison coverage, such as 23 of 24 periods, alongside native actual coverage such as 46 of 48 half-hours.
- MAE, bias, and RMSE, with short explanations.
- Largest overforecast periods and a CSV download.
- Actuals hidden in the decision view until the user reveals them.

## Metric definitions

For matched periods, define `error = forecast - actual`.

- **MAE:** average absolute error; typical miss in MW.
- **Bias:** average signed error; positive means wind was overforecast.
- **RMSE:** square root of average squared error; gives large misses more weight.

Exclude unmatched periods and show the number of matched samples. Missing is not zero. If converting average power to energy, multiply MW by the interval duration in hours.

## Important checks

- Forecasts published after the cutoff are excluded.
- The latest eligible forecast is selected, with a documented rule for duplicate records.
- Missing data remains visible and is excluded from metrics.
- Hand-calculated sample metrics match the code.
- January decision dates map to the correct next-day delivery dates.

Keep monthly analysis labelled retrospective. Do not use future outcomes as information available during an earlier buying decision.
