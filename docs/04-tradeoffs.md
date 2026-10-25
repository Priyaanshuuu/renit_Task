# My tradeoffs

I chose these tradeoffs to keep the pilot small while making its results reproducible and inspectable.

| Decision | Benefit | Limitation |
| --- | --- | --- |
| Prepared historical snapshot | Fast, reproducible analysis without upstream downloads on page load. | It does not automatically receive new data or later corrections. |
| SQLite | Simple setup and easy packaging. | Less suitable for a growing service with concurrent writes. |
| Two Vercel projects with a frontend API rewrite | Matches the chosen hosting and keeps browser requests on one origin. | The projects need compatible releases and a configured backend destination. I checked public backend readiness; automated hosted browser acceptance is separate from local tests. |
| Configurable cutoff | Supports an explicit buying-time assumption. | The real business cutoff still needs client confirmation. |
| Latest eligible forecast per delivery period | Uses the newest available information for each period. | A displayed curve may combine publication times; show them clearly. |
| Exclude missing pairs from metrics | Avoids inventing values. | Results describe only available pairs, so coverage must be visible. |
| MAE, bias, and RMSE | Easy to calculate and explain. | They measure forecast error, not the client's financial loss. |
| Only Elexon national wind data | Stays within the assignment. | Cannot represent the client's demand, contracts, or exact procurement needs. |
| January-only evaluation | Keeps the work focused. | Cannot establish performance across seasons or extreme conditions. |
| Hourly comparison using complete pairs of actual half-hours | Keeps native hourly forecast resolution without fabricating half-hour forecasts. | Loses half-hour detail and assumes a WINDFOR hour label represents the following hour; its response has no interval-end field. |
| Bounded publication extraction windows | Keeps the snapshot small and reproducible. | Actual corrections published after the recorded window may be absent. |
| UI-only outcome reveal | Supports a decision-first retrospective workflow without extra endpoints or authentication. | Actuals are present in the API response and inspectable; this is not access control. CSV is offered only after reveal and explicitly includes outcomes. |
| One route loader for daily and monthly requests | Keeps selection, cancellation, retry, and errors in one small flow. | Both requests run for each applied selection, and the page waits for both to settle. Monthly failure is shown separately after reveal. No caching is added for this bounded pilot. |

## Risks worth explaining

- Using a forecast published after the decision would make the evaluation unfairly optimistic.
- Different interval lengths or coverage between sources can make comparisons misleading unless checked.
- Historical actuals may have been revised. I record retrieval times and treat actuals as retrospective rather than information available at the earlier decision.
- A positive error indicates a wind shortfall relative to forecast. It is not automatically the client's purchase shortfall.

## What stays out of the first version

I kept custom prediction models, chatbots, Redis, message queues, microservices, and accounts outside the pilot. The two review workflows work without that infrastructure.
