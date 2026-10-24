# Historical wind snapshot: Step 2

Prepared and checked on 24 October 2026. This is an extraction from the two permitted Elexon datasets, not a live feed. Forecast selection and error calculations remain in Step 3.

## Source evidence

The public [Elexon developer portal](https://developer.data.elexon.co.uk/) explains that dataset endpoints filter by publication time and retain superseded data. It describes stream responses as JSON without a record-return limit. We use daily requests to keep downloads small and recoverable. Real responses were arrays, with no pagination envelope.

Only these data endpoints are used:

- [FUELHH stream documentation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream): `https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream`.
- [WINDFOR stream documentation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream): `https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`.

Those documentation pages require JavaScript in some clients. The filters were also checked against actual responses. Requests use `publishDateTimeFrom` and `publishDateTimeTo`; every returned publication timestamp is validated against that inclusive window. Delivery filtering is separate: `[2026-01-02T00:00Z, 2026-02-02T00:00Z)`.

Observed examples:

- A FUELHH publication request for 2 January included delivery at 1 January 23:30, published at 2 January 00:00, and delivery at 2 January 23:30, published at 3 January 00:00. This confirms publication filtering and included boundaries.
- WINDFOR publications on 1 January returned 584 records: eight publications with 73 hourly values each, including deliveries from 31 December through 3 January. The filter does not mean next-day delivery.
- WINDFOR supplies `dataset`, `publishTime`, `startTime`, and `generation`. FUELHH additionally supplies `fuelType`, `settlementDate`, and `settlementPeriod`. Only FUELHH `fuelType = WIND` enters SQLite. Other fuels returned by the source remain only in the ignored raw cache.

## Resolution, units, and comparison convention

Elexon's [FUELHH glossary](https://www.elexon.co.uk/bsc/glossary/half-hourly-generation-by-fuel-type/) defines half-hour average power in MW. Its [wind-generation information](https://bmrs.elexon.co.uk/wind-generation) describes hourly forecasts and operational metering coverage. Live records confirmed the half-hour FUELHH and hourly WINDFOR grids across the whole delivery window.

Preserve both native resolutions. For Step 3, compare the forecast labelled hour `H` with `(actual[H] + actual[H + 30 minutes]) / 2`. Require both actual half-hours; one missing value makes the comparison hour unavailable. Never interpolate, fill with zero, duplicate an hourly forecast into two independent samples, or sum MW as if it were energy.

**Explicit assumption:** WINDFOR has no interval-end or averaging field. Treating its hour label as representing `[H, H+1 hour)` is the pilot's comparison convention, not verified evidence that the forecast is an hourly average. The actual hourly mean is justified by its two equal-duration half-hour averages. Keep this limitation visible in later analysis, and retain native records so the convention can change without another download.

January London dates are UTC/GMT: each delivery day has 48 native actual half-hours and **24 comparison hours**. Report these separately. A future scope covering daylight-saving transitions must derive counts from the local calendar.

This covers Great Britain operationally metered wind visible to the system operator, not all UK or embedded wind and not the client's own generation allocation.

## Publication windows and revisions

| Dataset | Start, inclusive | End boundary, inclusive |
| --- | --- | --- |
| FUELHH | 2 January 2026 00:00 UTC | 3 February 2026 00:00 UTC |
| WINDFOR | 29 December 2025 00:00 UTC | 1 February 2026 00:00 UTC |

Adjacent daily requests share their boundary. Identical `(delivery_start, published_at, generation)` duplicates are collapsed. Different values for the same delivery/publication key stop the build; source row order never decides. Different publication times are preserved as revisions in both tables.

The three-day forecast lookback precedes the first supported decision cutoff. The initial lookback requests contained no target deliveries; the earliest retained forecast was published on 31 December at 02:30 UTC. The largest observed retained forecast lead was about 66.5 hours. This window covers the observed horizon, without promising an undocumented unlimited source history.

The actual publication window includes the last delivery day and a buffer. It does **not** guarantee inclusion of corrections published after 3 February. Later analysis must use the latest actual revision within this snapshot and explain that extraction boundary. Publication time is the availability proxy; historical receipt/network latency is unknown.

## Artifacts and commands

- [`data/wind_snapshot.sqlite`](../data/wind_snapshot.sqlite): native actual/forecast revisions and embedded provenance.
- [`data/wind_snapshot.report.json`](../data/wind_snapshot.report.json): exported coverage and provenance.
- `data/raw/`: ignored local daily response cache; unnecessary for running the eventual dashboard.
- [`backend/scripts/build_snapshot.py`](../backend/scripts/build_snapshot.py): explicit preparation command.
- [`backend/app/snapshot.py`](../backend/app/snapshot.py): validation, coverage counting, and SQLite construction.

Run from the repository root:

```powershell
# Download missing responses and build the snapshot.
& ./backend/.venv/Scripts/python.exe -m backend.scripts.build_snapshot

# Rebuild without network access after the local cache exists.
& ./backend/.venv/Scripts/python.exe -m backend.scripts.build_snapshot --offline

# Deliberately retrieve all responses again.
& ./backend/.venv/Scripts/python.exe -m backend.scripts.build_snapshot --refresh

# Optional alternate paths.
& ./backend/.venv/Scripts/python.exe -m backend.scripts.build_snapshot --offline --output ./data/review.sqlite --cache-dir ./data/raw

& ./backend/.venv/Scripts/python.exe -m pytest backend/tests -q
```

A fresh checkout includes the snapshot/report but must download the cache before an offline rebuild. Refreshes can pick up source changes. Preserve the report associated with a reviewed snapshot.

Network/selected transient HTTP failures have at most three attempts; permanent HTTP errors and invalid data fail immediately. Timeouts remain enabled. A server-requested retry delay above 30 seconds stops the build rather than retrying early.

Each request records URL, retrieval timestamp, row count, and SHA-256 of its canonical JSON record array. The report records build time, source attribution, normalization counts, units, alignment assumptions, and daily coverage. These hashes identify responses; they are not Elexon signatures. `built_at` changes on rebuilds even when records are unchanged.

The builder writes a separate candidate database, validates it, closes it, and atomically replaces the previous snapshot after success. The embedded report is authoritative if writing the sidecar fails. Runtime API reads must use SQLite `mode=ro`; the file is not made globally immutable through operating-system permissions. Requests never trigger downloads or rebuilds.

## SQLite schema, version 1

| Table | Columns | Key |
| --- | --- | --- |
| `wind_actuals` | `delivery_start`, `published_at`, `actual_mw` | Delivery + publication |
| `wind_forecasts` | `delivery_start`, `published_at`, `forecast_mw` | Delivery + publication |
| `snapshot_metadata` | `key`, `value` | `key`; `report` contains JSON |

Stored timestamps are UTC ISO strings with explicit `Z` and fixed six-digit fractional seconds, including `.000000` when needed. Format later SQL cutoff/range parameters through the same `utc_text` helper so lexical comparisons match chronological order, and parse before datetime arithmetic. Mixing timestamp precisions can otherwise incorrectly include a revision after the cutoff. Native tables include revisions published after earlier decisions: Step 3 must filter eligibility before selecting a forecast. No selected curves, hourly actual values, or error metrics are materialized here.

## Observed result

| Check | Result |
| --- | --- |
| Requests | 66: 32 FUELHH and 34 WINDFOR |
| FUELHH response rows | 31,360 across all fuels |
| Other-fuel rows excluded | 29,792 |
| WIND rows outside delivery window excluded | 49 |
| Identical WIND duplicate rows collapsed | 31, from request boundaries |
| Stored actuals | 1,488; all expected half-hours, no additional publication revisions observed |
| WINDFOR response rows | 19,856 |
| Forecast rows outside delivery window excluded | 1,992 |
| Stored forecast revisions | 17,864 for all 744 hours |
| Distinct retained publication times | 256 |
| Revisions per forecast hour | 8-32 |
| Actual coverage per day | 48/48 half-hours; 24/24 complete hourly pairs |
| Eligible forecast hours at 09:00 per decision day | 24/24 |
| Eligible forecast hours at midnight per decision day | 22/24; next-day 22:00 and 23:00 unavailable at that cutoff |
| Invalid required values / conflicting duplicates | None encountered; either causes build failure |

Having a forecast for all target hours somewhere in the extraction does not mean every hour was available at every cutoff. The report lists missing periods for the checked midnight and 09:00 cutoffs. General cutoff handling remains in Step 3.

Validation completed: live extraction, offline rebuild, SQLite integrity/read-only checks, matching embedded/sidecar metadata, and 23 focused offline tests. Tests cover validation, revision preservation, fractional-second cutoff ordering, gaps, caching, retry behavior, and retaining the previous snapshot after a candidate-write failure. These checks do not establish analysis API or deployed-app readiness.

Contains BMRS data © Elexon Limited copyright and database right 2026. Source: Elexon Insights Solution / National Energy System Operator. Keep source attribution with the bundled, displayed, and exported data.
