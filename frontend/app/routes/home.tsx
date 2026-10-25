import { useState } from "react";
import { Form, useNavigation, useRevalidator } from "react-router";
import type { Route } from "./+types/home";
import {
  analysisQuery,
  fetchAnalysis,
  fetchMonthlySummary,
  type Analysis,
  type Metrics,
  type MonthlySummary,
  type ApiResult,
} from "../lib/api";
import {
  formatDate,
  formatHour,
  formatInstant,
  formatNumber,
} from "../lib/format";
import { GenerationChart } from "../components/generation-chart";

export function meta(_: Route.MetaArgs) {
  return [
    { title: "GB wind · Forecast analysis" },
    {
      name: "description",
      content:
        "Explore the national wind forecast available at January 2026 buying decisions.",
    },
  ];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const params = new URL(request.url).searchParams;
  const decisionDate = params.get("decision_date") ?? "2026-01-01";
  const cutoffTime = params.get("cutoff_time") ?? "09:00";
  let [daily, monthly] = await Promise.all([
    fetchAnalysis(decisionDate, cutoffTime, request.signal),
    fetchMonthlySummary(cutoffTime, request.signal),
  ]);
  if (
    daily.data &&
    (daily.data.decision_date !== decisionDate ||
      formatHour(daily.data.decision_cutoff_at) !== cutoffTime)
  ) {
    daily = {
      error: "The API response does not match this selection. Please retry.",
    };
  }
  if (monthly.data && monthly.data.cutoff_time !== cutoffTime) {
    monthly = {
      error: "The monthly response does not match this cutoff. Please retry.",
    };
  }
  return { decisionDate, cutoffTime, daily, monthly };
}

function Header() {
  return (
    <header className="site-header">
      <div className="header-inner">
        <a href="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            ~
          </span>{" "}
          GB wind
          <span className="brand-divider" />
          Forecast analysis
        </a>
        <span className="pilot-label">HISTORICAL PILOT · JAN 2026</span>
      </div>
    </header>
  );
}

export default function Home({ loaderData }: Route.ComponentProps) {
  const { decisionDate, cutoffTime, daily, monthly } = loaderData;
  const navigation = useNavigation();
  const revalidator = useRevalidator();
  const pending = navigation.state !== "idle" || revalidator.state !== "idle";
  return (
    <>
      <Header />
      <main className="dashboard">
        <div className="page-intro">
          <div>
            <p className="eyebrow">GREAT BRITAIN · NATIONAL GENERATION</p>
            <h1>National wind, at decision time.</h1>
            <p>
              See the forecast available before a decision. Then explore how the
              next day unfolded.
            </p>
          </div>
          <span className="snapshot-tag">
            <span /> Prepared snapshot
          </span>
        </div>
        <Form method="get" className="controls" preventScrollReset>
          <label>
            Decision date
            <input
              key={decisionDate}
              type="date"
              name="decision_date"
              min="2026-01-01"
              max="2026-01-31"
              defaultValue={decisionDate}
              required
            />
          </label>
          <label>
            Decision cutoff
            <input
              key={cutoffTime}
              type="time"
              name="cutoff_time"
              defaultValue={cutoffTime}
              step="60"
              required
            />
          </label>
          <div className="control-context">
            <strong>
              Europe/London <span>· GMT in January</span>
            </strong>
            <small>
              Next-day delivery · Cutoff is an illustrative assumption
            </small>
          </div>
          <button className="primary" type="submit">
            Apply selection <span aria-hidden="true">→</span>
          </button>
        </Form>
        <div aria-live="polite" aria-busy={pending}>
          {pending ? (
            <p role="status" className="notice">
              Loading the selected decision and monthly summary...
            </p>
          ) : daily.data ? (
            <Results
              key={`${decisionDate}/${cutoffTime}`}
              analysis={daily.data}
              monthly={monthly}
              cutoffTime={cutoffTime}
            />
          ) : (
            <div role="alert" className="notice error">
              <h2>Analysis could not be loaded</h2>
              <p>{daily.error}</p>
              <button
                className="secondary"
                onClick={() => revalidator.revalidate()}
              >
                Retry requests
              </button>
            </div>
          )}
        </div>
        <footer className="scope-note">
          GB operationally metered national wind. This is not a customer's own
          generation or purchase requirement. Decision dates: 1-31 January 2026;
          delivery dates: 2 January-1 February.
        </footer>
      </main>
    </>
  );
}

function MetricCards({ metrics }: { metrics: Metrics }) {
  const cards = [
    {
      label: "Mean absolute error",
      value: metrics.mae_mw,
      description: "Average error magnitude",
    },
    {
      label: "Bias",
      value: metrics.bias_mw,
      description: "Positive means overforecast",
    },
    {
      label: "Root mean square error",
      value: metrics.rmse_mw,
      description: "More weight on larger errors",
    },
  ];
  return (
    <div className="metric-grid">
      {cards.map(({ label, value, description }) => (
        <div className="metric" key={label}>
          <p>{label}</p>
          <strong>
            {formatNumber(value)} <span>MW</span>
          </strong>
          <small>{description}</small>
        </div>
      ))}
    </div>
  );
}

function Results({
  analysis,
  monthly,
  cutoffTime,
}: {
  analysis: Analysis;
  monthly: ApiResult<MonthlySummary>;
  cutoffTime: string;
}) {
  const [view, setView] = useState<"decision" | "accuracy">("decision");
  const [revealed, setRevealed] = useState(false);
  const showActuals = view === "accuracy" || revealed;
  const { coverage, intervals } = analysis;
  const revalidator = useRevalidator();
  return (
    <>
      <div className="view-bar">
        <div className="view-switch" role="group" aria-label="Analysis view">
          <button
            aria-pressed={view === "decision"}
            onClick={() => {
              setView("decision");
              setRevealed(false);
            }}
          >
            Decision view
          </button>
          <button
            aria-pressed={view === "accuracy"}
            onClick={() => setView("accuracy")}
          >
            Accuracy view
          </button>
        </div>
        <p>
          {showActuals
            ? "Retrospective · outcomes visible"
            : "Decision view · outcomes hidden"}
        </p>
      </div>
      <section className="card" aria-labelledby="delivery-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">NEXT-DAY DELIVERY</p>
            <h2 id="delivery-heading">{formatDate(analysis.delivery_date)}</h2>
            <p>
              Decision: {formatInstant(analysis.decision_cutoff_at)} · Latest
              eligible forecast per hour
            </p>
          </div>
          <div className="coverage-badge">
            <strong>
              {coverage.forecast_hours} / {coverage.expected_hours}
            </strong>
            <span>forecast hours</span>
          </div>
        </div>
        <div className="chart-heading">
          <span>Generation · MW</span>
          <div className="legend">
            <span>
              <i className="forecast-line" />
              Forecast at cutoff
            </span>
            {showActuals && (
              <span>
                <i className="actual-line" />
                Actual generation
              </span>
            )}
          </div>
        </div>
        {coverage.forecast_hours === 0 && (
          <p role="status" className="notice">
            No eligible forecast is available at this cutoff. Missing hours are
            left blank.
          </p>
        )}
        {intervals.length > 0 ? (
          <GenerationChart intervals={intervals} showActuals={showActuals} />
        ) : (
          <p className="notice">
            No delivery intervals were returned for this selection.
          </p>
        )}
        <div className="chart-footnote">
          <span>Hourly comparison · Europe/London (GMT)</span>
          <span>
            {coverage.forecast_hours < coverage.expected_hours
              ? `${coverage.expected_hours - coverage.forecast_hours} forecast hours unavailable. Gaps are not filled.`
              : "All forecast hours available at this cutoff."}
          </span>
        </div>
        {!showActuals && (
          <div className="reveal-panel">
            <div>
              <strong>Start with what was known.</strong>
              <p>
                Actual generation, errors, and monthly outcomes are hidden until
                you reveal them.
              </p>
            </div>
            <button className="secondary" onClick={() => setRevealed(true)}>
              Reveal outcomes
            </button>
          </div>
        )}
      </section>
      {showActuals && (
        <>
          <section className="card" aria-labelledby="accuracy-heading">
            <div className="section-heading">
              <div>
                <p className="eyebrow">DAILY ACCURACY</p>
                <h2 id="accuracy-heading">Forecast versus outcome</h2>
                <p>
                  Error = forecast - actual. Positive errors are overforecasts.
                </p>
              </div>
              <span className="muted">
                {coverage.matched_hours} / {coverage.expected_hours} matched
                hours
              </span>
            </div>
            <MetricCards metrics={analysis.metrics} />
            <p className="detail-note">
              Actual coverage: {coverage.actual_hours}/{coverage.expected_hours}{" "}
              hours · {coverage.available_actual_half_hours}/
              {coverage.expected_actual_half_hours} native half-hours. Metrics
              use {analysis.metrics.sample_count} matched pairs only.
              {analysis.metrics.sample_count === 0 &&
                " No matched pairs; accuracy metrics are unavailable."}
            </p>
            <h3>Largest overforecasts</h3>
            {analysis.largest_overforecasts.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Delivery hour (GMT)</th>
                      <th>Forecast · MW</th>
                      <th>Actual · MW</th>
                      <th>Error · MW</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.largest_overforecasts.map((item) => (
                      <tr key={item.delivery_start}>
                        <th>
                          {formatHour(item.delivery_start)}-
                          {formatHour(item.delivery_end)}
                        </th>
                        <td>{formatNumber(item.forecast_mw)}</td>
                        <td>{formatNumber(item.actual_mw)}</td>
                        <td className="positive">
                          +{formatNumber(item.error_mw)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="detail-note">
                No positive matched errors for this selection.
              </p>
            )}
          </section>
          <section className="card monthly" aria-labelledby="monthly-heading">
            <div className="section-heading">
              <div>
                <p className="eyebrow">RETROSPECTIVE · JANUARY 2026</p>
                <h2 id="monthly-heading">The month at {cutoffTime}</h2>
                <p>
                  31 separate next-day decisions, each using its own{" "}
                  {cutoffTime} Europe/London cutoff.
                </p>
              </div>
            </div>
            {monthly.data ? (
              <>
                <MetricCards metrics={monthly.data.metrics} />
                <p className="detail-note">
                  {monthly.data.coverage.matched_hours}/
                  {monthly.data.coverage.expected_hours} matched hours ·{" "}
                  {monthly.data.coverage.forecast_hours} forecast hours ·{" "}
                  {monthly.data.coverage.actual_hours} actual hours. Metrics
                  pool matched periods; they are not averages of daily metrics.
                </p>
              </>
            ) : (
              <div role="alert" className="notice error">
                <p>{monthly.error}</p>
                <button
                  className="secondary"
                  onClick={() => revalidator.revalidate()}
                >
                  Retry requests
                </button>
              </div>
            )}
          </section>
        </>
      )}
      <section className="card" aria-labelledby="data-heading">
        <div className="section-heading">
          <div>
            <h2 id="data-heading">Inspect the data</h2>
            <p>
              Publication timestamps and missing intervals, with the same
              decision cutoff.
            </p>
          </div>
          {showActuals && (
            <a
              className="secondary"
              href={`/api/analysis.csv?${analysisQuery(analysis.decision_date, cutoffTime)}`}
              download
            >
              Download CSV · includes outcomes
            </a>
          )}
        </div>
        <details>
          <summary>Hourly data · {intervals.length} intervals</summary>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Delivery (GMT)</th>
                  <th>Forecast · MW</th>
                  <th>Forecast published (GMT)</th>
                  {showActuals && (
                    <>
                      <th>Actual · MW</th>
                      <th>Error · MW</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {intervals.map((item) => (
                  <tr key={item.delivery_start}>
                    <th>
                      {formatHour(item.delivery_start)}-
                      {formatHour(item.delivery_end)}
                    </th>
                    <td>{formatNumber(item.forecast_mw)}</td>
                    <td>
                      {item.forecast_published_at
                        ? formatInstant(item.forecast_published_at)
                        : "No eligible forecast"}
                    </td>
                    {showActuals && (
                      <>
                        <td>{formatNumber(item.actual_mw)}</td>
                        <td>{formatNumber(item.error_mw)}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
        <details>
          <summary>Source, extraction & limitations</summary>
          <div className="source-details">
            <p>{analysis.source.provider}</p>
            <p>
              Snapshot built {formatInstant(analysis.source.built_at)}.
              Retrieval completed{" "}
              {formatInstant(analysis.source.retrieval_finished_at)}. This is
              historical snapshot data, not a live feed.
            </p>
            <p>{analysis.source.alignment_rule}</p>
            <ul>
              {analysis.source.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
            <p>{analysis.source.attribution}</p>
          </div>
        </details>
      </section>
    </>
  );
}
