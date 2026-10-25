# Dashboard reference

Implemented in Step 5 on 25 October 2026. This is the local dashboard against the prepared historical snapshot; Docker and public deployment remain Step 6.

## Workflow

The single page starts at decision date `2026-01-01`, cutoff `09:00`. The date picker accepts 1-31 January 2026; the cutoff is local `HH:MM` in Europe/London. Select **Apply selection** to load the next delivery day. The applied inputs live in `decision_date` and `cutoff_time` URL parameters, so refresh and bookmarks preserve them. Edits are drafts until applied; the delivery heading always labels the displayed result's effective decision timestamp.

Decision view shows only the eligible forecast and forecast coverage. Actuals are excluded from the chart data, axis scaling, tooltip, and hourly table. Daily outcome metrics, overforecasts, the retrospective monthly summary, and the CSV link are absent until **Reveal outcomes** or **Accuracy view** is selected. Returning to Decision view hides them. Applying or retrying a selection resets the view to hidden outcomes.

The API response itself contains outcomes; reveal is a presentation workflow, not access control. CSV includes actuals and errors and is explicitly labelled accordingly. Its query matches the applied decision and cutoff, and it is absent during pending requests.

Accuracy displays the Python-calculated MAE, bias, RMSE, matched coverage, native actual coverage, and up to five largest positive errors. Error is forecast minus actual: positive means overforecast. The monthly card is labelled retrospective and applies the chosen cutoff separately to all 31 decisions. React formats these values to at most one decimal place; it does not recalculate metrics or forecast eligibility.

## Data and failure handling

- A Framework `clientLoader` requests the daily analysis and monthly summary concurrently. Both settle before displaying the selection. Each has an independent success/error result; a failed month does not discard a successful day.
- The router request's abort signal is forwarded to `fetch`. Interrupted navigation is cancelled, and obsolete responses cannot commit over a newer selection. Old results and CSV are removed while loading.
- Small runtime guards check the response fields used by the page, including dates, finite/null numbers, collections, provenance, and the applied selection. Unexpected shapes show an error rather than invented values. The API remains the authority for the full response contract.
- Invalid input (`422`), unavailable snapshot (`503`), other failed statuses, malformed responses, and network failures produce short messages with retry. Raw server bodies and tracebacks are not displayed.
- Missing forecast/actual values stay null. Recharts uses `connectNulls={false}`; missing hours remain gaps. Tables distinguish `Unavailable` from `0`. No matched samples yields unavailable metrics, with an explanation.
- Forecast publication times are available in chart tooltips, including keyboard navigation, and in the expandable hourly table. The final hour ends at `00:00` on the following day; the section heading identifies its delivery day.
- Source details include provider, attribution, snapshot build/retrieval completion, the hourly alignment assumption, and source limitations. This is a prepared snapshot, not a live feed.

## Code map

| File | Responsibility |
| --- | --- |
| `frontend/app/routes/home.tsx` | URL loading, controls, view/reveal state, daily and monthly presentation, export link |
| `frontend/app/lib/api.ts` | Used response types, runtime shape checks, API requests and safe failure messages |
| `frontend/app/lib/format.ts` | MW number and explicit Europe/London date/time formatting |
| `frontend/app/components/generation-chart.tsx` | Forecast/actual Recharts presentation and publication tooltip |
| `frontend/app/root.tsx` | Document shell and root SPA loading fallback |
| `frontend/app/app.css` | Responsive styling using the existing Tailwind setup and system font fallbacks |
| `frontend/tests/dashboard.spec.ts` | Focused real-data and intercepted-failure browser checks |

No extra component framework, query/state library, frontend metric implementation, new backend endpoint, or snapshot change was needed. Recharts is the only added runtime dependency; Playwright and Prettier are development tools. The npm lockfile records resolved versions.

## Verification

Local checks passed: frontend type checking and production build, 97 Python tests, and six Chrome browser checks. The Python run retains the existing Starlette/HTTPX deprecation warning; no backend dependencies were changed in this step.

Run commands from [the root README](../README.md) and [frontend README](../frontend/README.md). Browser checks require both local servers and the bundled snapshot. Chrome was used locally; no claim is made about Firefox, Safari, deployed hosting, Docker, or a screen-reader audit.

Real snapshot checks cover hidden outcomes, explicit reveal and Accuracy view, publication tooltip/table, JSON versus CSV numeric agreement for all 24 intervals, the 31 January to 1 February boundary, and default versus midnight coverage. At `09:00`, monthly coverage is `744/744`; midnight is `682/744`. The midnight daily view reports `22/24` forecast hours.

Intercepted checks delay a real response to verify cancellation, return unavailable/failed API responses to verify retry and independent monthly errors, and inject an interior null plus zero/no matched actuals to verify chart gaps, zero preservation, and unavailable metrics. These are synthetic browser scenarios, not claims that the packaged snapshot contains those failures.

Desktop (1440px) and narrow (390px and 320px) screenshots are generated by the checks. Tables scroll inside their cards; controls and page content fit without horizontal page overflow. Semantic labels, native form controls, pressed-state view buttons, focus outlines, loading/error announcements, and an accessible table alternative support keyboard use.

## References for future changes

Reviewed on 25 October 2026 against installed React Router `8.5.0`, Recharts `3.10.1`, and Playwright `1.64.1`:

- [React Router Framework data loading](https://reactrouter.com/start/framework/data-loading): route-owned `clientLoader` and generated route types. Installed version docs are under `frontend/node_modules/react-router/docs/`.
- [React Router SPA mode](https://reactrouter.com/how-to/spa): root-only `HydrateFallback` and build-time rendering even with `ssr: false`.
- [Pending UI](https://reactrouter.com/start/framework/pending-ui) and [race conditions](https://reactrouter.com/explanation/race-conditions): GET form navigation, pending state, and cancellation.
- [Recharts LineChart API](https://recharts.github.io/en-US/api/LineChart/): responsive chart composition, tooltip, separate series, and axis labels. Preserve explicit null gaps and exclude outcomes before reveal.
- [Playwright configuration](https://playwright.dev/docs/test-configuration) and [browser channels](https://playwright.dev/docs/api/class-testoptions#test-options-channel): a small local browser check suite using an installed browser.

Keep these references version-aware. Additional features remain in the advanced/future-scope documents; this dashboard does not authorize starting deployment.
