# A more advanced approach

These are possible improvements, not features already implemented. They become useful when the pilot turns into a daily operational tool.

## 1. Automatic data updates

Run scheduled ingestion instead of preparing a snapshot manually. Add retries, duplicate-safe writes, and alerts for missing or stale data.

Why: users can work with new forecasts every day.

## 2. A persistent database

Move to PostgreSQL when the app needs ongoing writes, longer history, or multiple users. Index delivery time and publication time and preserve forecast revisions.

Why: it supports a growing dataset and repeatable historical decisions.

## 3. More detailed forecast evaluation

Compare errors by time of day and forecast lead time. Compare different decision cutoffs using the same evaluation periods.

Why: a single monthly average can hide when forecasts perform poorly.

## 4. Historical uncertainty ranges

Use earlier forecast errors to estimate a plausible range around a forecast. Test the range on later, unseen periods and show how often actual generation falls inside it.

Why: buyers can see uncertainty rather than only one predicted value.

Do not build a range from future outcomes. A small January sample may be insufficient, so this may need more historical data and an agreed scope extension.

## 5. Stronger traceability

Record source retrieval times, dataset versions, and the exact forecast selected for each decision. Add monitoring for failed updates and unusual data changes.

Why: a reviewer can reproduce what the user saw and how the numbers were calculated.

## Why defer these?

The assignment is a one-month pilot with a 16-hour limit. Correct forecast selection, clear charts, and reliable metrics provide more value now than extra infrastructure.
