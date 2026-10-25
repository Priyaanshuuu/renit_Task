# Historical wind data

I prepared `wind_snapshot.sqlite` from Great Britain WIND actuals and forecast revisions for delivery dates 2 January-1 February 2026. `wind_snapshot.report.json` contains coverage and source request provenance. The same report is embedded in SQLite.

See [the snapshot reference](../docs/07-data-snapshot.md) for the schema, commands, comparison assumption, extraction windows, and limitations.

I keep the local `raw/` download cache out of Git and bundle the snapshot and report with the app. The API opens SQLite in read-only mode and preserves missing values.

Contains BMRS data © Elexon Limited copyright and database right 2026. Source: Elexon Insights Solution / National Energy System Operator. Coverage is operationally metered GB wind, not all UK or embedded wind.
