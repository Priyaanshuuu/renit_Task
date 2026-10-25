# My selection and calculation rules

I implemented and checked these Python calculations on 24 October 2026. They operate on the prepared snapshot and are shared by the [API](09-api-reference.md) and [dashboard](10-dashboard.md).

## Code and inputs

- [`backend/app/analysis.py`](../backend/app/analysis.py): decision windows, revision selection, hourly comparisons, daily/monthly results, and metrics. It imports no FastAPI code and performs no file or network access.
- [`backend/app/storage.py`](../backend/app/storage.py): reads the small SQLite snapshot with `mode=ro`, loads native records and embedded source metadata, and closes the connection before returning. A missing path fails without creating an empty database. Unsupported schema versions fail explicitly.
- [`backend/tests/test_analysis.py`](../backend/tests/test_analysis.py): synthetic boundary tests and offline checks against the bundled snapshot.

`analyze_day(decision_date, actuals, forecasts, cutoff_time=...)` accepts January 2026 decision dates and a local minute-precision `datetime.time`, defaulting to `09:00`. The cutoff is interpreted in `Europe/London` and converted to UTC. Offset-bearing times and nonzero seconds/microseconds are rejected. Exact URL string-format validation is defined in the API query models.

The next local calendar day defines the delivery range, from its midnight inclusive to the following midnight exclusive. January 31 therefore maps to February 1, with February 2 midnight excluded. The expected comparison grid is derived from these bounds; it has 24 hours in the supported January scope.

## Selection and matching rules

1. Restrict records to the delivery window.
2. For forecasts, exclude every publication after the decision cutoff **before** selecting a revision. A publication exactly at the cutoff is eligible.
3. For each forecast delivery hour, choose the eligible record with the latest publication time. Input order does not decide the result. Identical duplicates do not inflate counts; conflicting values for an eligible delivery/publication key fail explicitly.
4. Actuals are retrospective: independently choose the latest publication per native half-hour available within the snapshot. They are not filtered by the earlier buying cutoff. Later corrections outside the extraction window remain unknown.
5. For hour `H`, average actuals at `H` and `H+30min` only when both exist. Preserve their publication times in that order. Missing forecasts or incomplete actual pairs remain unavailable; there is no interpolation or gap filling.
6. Calculate `error_mw = forecast_mw - actual_mw` only for matched pairs. Zero generation and zero error are valid observations.

The hourly alignment is the explicit pilot assumption recorded in [the snapshot reference](07-data-snapshot.md). It does not establish that WINDFOR defines its values as hour averages. National metered wind remains a proxy for forecast quality, not the client's exact procurement requirement.

## Results and coverage

Every daily result contains all 24 delivery hours in chronological order, including gaps. Each interval contains start/end, selected forecast and publication time, hourly actual, the two native actual publication times, and error. Unavailable values are Python `None`, serialized as JSON `null` by the API.

Coverage reports separate counts:

| Field | Meaning |
| --- | --- |
| `expected_hours` | Expected hourly comparison periods |
| `forecast_hours` | Hours with an eligible selected forecast |
| `actual_hours` | Hours with both actual half-hours available |
| `matched_hours` | Hours with both forecast and complete actual pair |
| `expected_actual_half_hours` | Native actual periods expected |
| `available_actual_half_hours` | Distinct native actual periods available after revision selection |

I return typed dataclasses to keep calculations independent of the Pydantic HTTP boundary. They consume the validated native `GenerationRecord` format from snapshot preparation. My calculations use Python's standard date/time and math tools.

## Metrics and monthly aggregation

All metrics use the same matched errors, without display rounding:

- MAE: mean absolute error in MW.
- Bias: mean signed error in MW. Positive means wind was overforecast.
- RMSE: square root of mean squared error in MW.
- `sample_count`: number of matched hourly errors.

With no matched pairs, the count is zero and all three metrics are `None`. Non-finite input errors fail rather than producing misleading results.

`largest_overforecasts` contains up to five matched periods with strictly positive errors, ordered by descending error and then ascending delivery time to break ties. Negative errors, zeros, and missing pairs are excluded.

`analyze_month` repeats the analysis for each January decision using that day's cutoff and next-day delivery window. It sums coverage and pools the matched hourly errors before calculating monthly metrics. It does not average daily MAE/RMSE, substitute a month-end cutoff for earlier decisions, or fill days with missing observations. Monthly results are retrospective.

## Reproduce a daily result

Run from the repository root:

```powershell
& ./backend/.venv/Scripts/python.exe -c "from datetime import date; from backend.app.storage import read_snapshot; from backend.app.analysis import analyze_day; data=read_snapshot(); result=analyze_day(date(2026,1,15),data.actuals,data.forecasts); print(result.coverage); print(result.metrics)"

& ./backend/.venv/Scripts/python.exe -m pytest backend/tests -q
```

The reader defaults to the bundled `data/wind_snapshot.sqlite`, resolving its path from the module location rather than an assumed working directory. Explicit `Path` arguments support fixture snapshots and later configuration. The examples run from the root so Python can import the `backend` package.

## Real-data trace and validation

I cross-checked all 24 hours for the 15 January decision using independent SQL queries and `Decimal` arithmetic. It checked the selected eligible revision, both native actuals, hourly mean, errors, and all three daily metrics. The snapshot's SHA-256 was unchanged after analysis.

Example first delivery hour:

| Item | Observed value |
| --- | --- |
| Decision cutoff | 15 January 2026 09:00 UTC / Europe/London |
| Delivery interval | 16 January 00:00-01:00 UTC |
| Latest eligible forecast publication | 15 January 07:30 UTC |
| Selected forecast | 7,398 MW |
| Earlier eligible values | 7,848 MW at 04:30 and 8,337 MW at 02:30 on 15 January |
| Native actual at 00:00 | 7,477 MW, published 00:30 |
| Native actual at 00:30 | 7,194 MW, published 01:00 |
| Hourly actual mean | 7,335.5 MW |
| Signed error | +62.5 MW |

For that complete delivery day: 24 matched hours; MAE **782.75 MW**, bias **351.958333 MW**, RMSE **926.004680 MW**. These display values are rounded here; the calculation retains full float precision.

| January decision cutoff | Expected hours | Matched hours | MAE (MW) | Bias (MW) | RMSE (MW) |
| --- | --- | --- | --- | --- | --- |
| 09:00 Europe/London | 744 | 744 | 2,038.912634 | 1,747.887097 | 2,504.758653 |
| 00:00 Europe/London | 744 | 682 | 2,119.143695 | 1,793.608504 | 2,590.429558 |

Both runs have all 1,488 native actual half-hours and 744 complete actual hours. At midnight each decision lacks forecasts for the next day's 22:00 and 23:00 periods. Comparing accuracy across different cutoffs requires a common matched-period set; these totals verify each cutoff's calculation and coverage separately.

The largest positive hourly error in the default 09:00 run is **6,870 MW**, for 12 January 01:00-02:00 delivery. This describes a national wind overforecast, not a quantified client purchase shortfall or financial loss.

At the analysis stage, **50 tests passed** across snapshot preparation and analysis. Coverage includes exact-cutoff/fractional-second boundaries, latest revisions, duplicates, missing pairs, zero values, signed/hand-calculated metrics, unequal daily coverage in monthly aggregation, month-boundary mapping, read-only storage, and both real monthly cutoff runs. The independent SQL/Decimal trace also passed. API and browser checks are recorded separately in their references. These calculation checks alone do not establish Docker or hosted-app acceptance.
