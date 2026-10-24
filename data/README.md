# Historical wind data

`wind_snapshot.sqlite` contains Great Britain WIND actuals and forecast revisions for delivery dates 2 January-1 February 2026. `wind_snapshot.report.json` contains coverage and source request provenance. The same report is embedded in SQLite.

See [the snapshot reference](../docs/07-data-snapshot.md) for the schema, commands, comparison assumption, extraction windows, and limitations.

The local `raw/` download cache is ignored by Git. The snapshot and report are intended to be bundled with the app. API reads must use read-only mode and preserve missing-data behavior.

Contains BMRS data © Elexon Limited copyright and database right 2026. Source: Elexon Insights Solution / National Energy System Operator. Coverage is operationally metered GB wind, not all UK or embedded wind.
