# Improvements I would consider beyond the pilot

I have kept these ideas outside the current implementation. They would become useful if the historical pilot grew into a daily operational tool.

## Automatic data updates

I would add scheduled ingestion, bounded retries, duplicate-safe writes, and warnings for missing or stale data when new forecasts are needed each day. The current snapshot is rebuilt explicitly outside request handling.

## A persistent database

I would consider PostgreSQL for ongoing writes or a longer history, with indexes on delivery and publication time and preserved forecast revisions. Multiple users alone would not require this change while the data remains read-only.

## More detailed evaluation

I would compare errors by delivery hour and forecast lead time, and compare cutoffs on a common set of matched periods. This would help explain patterns that a monthly average can hide.

## Historical uncertainty ranges

With enough earlier data and an agreed scope extension, I would estimate ranges from past forecast errors and evaluate them on later, unseen periods. I would report how often actuals fall inside those ranges and avoid using future outcomes to construct them.

## Operational traceability

The pilot already records retrieval times, source provenance, selected forecast publications, and extraction assumptions. For an operational service, I would add durable records of viewed decisions, dataset versions, and monitoring for failed updates or unusual changes.

## Infrastructure I would add only when needed

| Option | When I would reconsider it |
| --- | --- |
| ORM and migrations | Regular schema changes or ongoing writes |
| Background queue | Durable work that needs to run independently of requests |
| Shared cache | Measured latency or upstream traffic justifies it |
| Generated API client and versioning | Independent consumers need a maintained public contract |
| Central tracing and monitoring | Existing logs no longer explain operational failures adequately |
| Additional service or repository layers | Concrete reuse or complexity makes the current modules hard to maintain |

Readable names, typed contracts, resource cleanup, useful failures, and focused tests are already part of my approach. I documented those in [the engineering conventions](06-engineering-conventions.md). The 16-hour brief is why I prioritised correctness and inspectable results over additional services.
