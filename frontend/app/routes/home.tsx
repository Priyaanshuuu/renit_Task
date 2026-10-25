import type { Route } from "./+types/home";

export function meta(_: Route.MetaArgs) {
  return [
    { title: "Great Britain Wind Forecast Analysis" },
    {
      name: "description",
      content: "National wind forecast analysis for January 2026 buying decisions.",
    },
  ];
}

export default function Home() {
  return (
    <main className="mx-auto max-w-3xl space-y-8 px-6 py-16">
      <header className="space-y-3">
        <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
          January 2026 pilot
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">
          Great Britain wind forecast analysis
        </h1>
        <p className="text-gray-600 dark:text-gray-300">
          Compare the national wind forecast available at a buying decision with
          actual generation for the following delivery day.
        </p>
      </header>

      <section aria-labelledby="scope-heading" className="space-y-3">
        <h2 id="scope-heading" className="text-xl font-semibold">
          Agreed pilot scope
        </h2>
        <ul className="list-disc space-y-2 pl-5">
          <li>Decision dates: 1–31 January 2026.</li>
          <li>Next-day delivery dates: 2 January–1 February 2026.</li>
          <li>
            Planned configurable cutoff: 09:00 Europe/London by default. This is
            an illustrative assumption, not a confirmed market deadline.
          </li>
          <li>Sources: Elexon FUELHH wind actuals and WINDFOR forecasts only.</li>
        </ul>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          National generation does not represent the client’s own supply or exact
          purchase requirement.
        </p>
      </section>

      <section aria-labelledby="status-heading" className="space-y-3">
        <h2 id="status-heading" className="text-xl font-semibold">
          Project status
        </h2>
        <p>
          The application scaffold and historical data snapshot are in place.
          Python forecast selection and calculations are implemented. The Decision
          and Accuracy views are not connected yet. This page does not display
          analysis data.
        </p>
        <a
          href="/api/health"
          className="inline-block underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4"
        >
          Check API process health
        </a>
      </section>
    </main>
  );
}
