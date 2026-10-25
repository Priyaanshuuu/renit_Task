import { test, expect, type Page } from "@playwright/test";

const selectedDay = "/?decision_date=2026-01-15&cutoff_time=09%3A00";

async function apply(page: Page, decisionDate: string, cutoffTime: string) {
  await page.getByLabel("Decision date", { exact: true }).fill(decisionDate);
  await page.getByLabel("Decision cutoff", { exact: true }).fill(cutoffTime);
  await page.getByRole("button", { name: "Apply selection" }).click();
}

test("real snapshot: Decision hides outcomes; reveal, publication details and CSV agree with the API", async ({
  page,
  request,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const response = await request.get(
    "/api/analysis?decision_date=2026-01-15&cutoff_time=09:00",
  );
  expect(response.ok()).toBeTruthy();
  const analysis = await response.json();
  await page.goto(selectedDay);
  await expect(
    page.getByRole("heading", { name: "16 Jan 2026" }),
  ).toBeVisible();
  await expect(page.locator(".coverage-badge")).toContainText("24 / 24");
  await expect(page.locator(".recharts-line-curve")).toHaveCount(1);
  await expect(
    page.getByRole("heading", { name: "Forecast versus outcome" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "The month at 09:00" }),
  ).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Download CSV/ })).toHaveCount(0);
  await page.getByText("Hourly data · 24 intervals", { exact: true }).click();
  const firstRow = page.locator("details table tbody tr").first();
  await expect(firstRow.locator("td")).toHaveCount(2);
  await expect(firstRow).toContainText("15 Jan 2026, 07:30 GMT");
  // Recharts keyboard navigation exposes the same publication timestamp.
  await page.locator(".recharts-surface").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator(".chart-tooltip")).toContainText("Published:");
  await expect(page.locator(".chart-tooltip")).not.toContainText("Actual:");
  await page.screenshot({
    path: info.outputPath("desktop-decision.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Reveal outcomes" }).click();
  await expect(page.locator(".recharts-line-curve")).toHaveCount(2);
  const accuracy = page.getByRole("region", {
    name: "Forecast versus outcome",
  });
  await expect(accuracy).toContainText("782.8");
  await expect(accuracy).toContainText("352");
  await expect(accuracy).toContainText("926");
  await expect(page.locator(".monthly")).toContainText("744/744 matched hours");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: /Download CSV/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(
    "wind-analysis-2026-01-15-0900.csv",
  );
  const stream = await download.createReadStream();
  let csv = "";
  for await (const chunk of stream!) csv += chunk;
  expect(csv.trim().split(/\r?\n/)).toHaveLength(25);
  // These first columns have no quoted text. Compare numbers, since CSV may
  // preserve a float suffix (7398.0) that JSON omits (7398).
  const csvValues = csv
    .trim()
    .split(/\r?\n/)
    .slice(1)
    .map((row) => row.split(",").slice(7, 10).map(Number));
  expect(csvValues).toEqual(
    analysis.intervals.map(
      (item: { forecast_mw: number; actual_mw: number; error_mw: number }) => [
        item.forecast_mw,
        item.actual_mw,
        item.error_mw,
      ],
    ),
  );
  await page
    .getByText("Source, extraction & limitations", { exact: true })
    .click();
  await expect(page.locator(".source-details")).toContainText("Elexon");
  await page.screenshot({
    path: info.outputPath("desktop-outcomes.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("real snapshot: midnight preserves missing forecast hours and January 31 delivers February 1", async ({
  page,
}) => {
  await page.goto(selectedDay);
  await page
    .getByRole("button", { name: "Accuracy view", exact: true })
    .click();
  await apply(page, "2026-01-31", "00:00");
  await expect(
    page.getByRole("heading", { name: "1 Feb 2026", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".coverage-badge")).toContainText("22 / 24");
  await expect(
    page.getByText("2 forecast hours unavailable. Gaps are not filled."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Decision view", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".monthly")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Accuracy view", exact: true })
    .click();
  await expect(page.locator(".monthly")).toContainText("682/744 matched hours");
  await page.getByText("Hourly data · 24 intervals", { exact: true }).click();
  await expect(page.locator("details table tbody tr").last()).toContainText(
    "No eligible forecast",
  );
  await page
    .getByRole("button", { name: "Decision view", exact: true })
    .click();
  await expect(page.getByRole("link", { name: /Download CSV/ })).toHaveCount(0);
});

test("delayed real response cannot replace a newer selection; pending results and export stay hidden", async ({
  page,
}) => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let entered!: () => void;
  const started = new Promise<void>((resolve) => {
    entered = resolve;
  });
  let completed!: () => void;
  const oldResponseFinished = new Promise<void>((resolve) => {
    completed = resolve;
  });
  await page.route("**/api/analysis?**", async (route) => {
    if (
      new URL(route.request().url()).searchParams.get("decision_date") !==
      "2026-01-14"
    )
      return route.continue();
    const response = await route.fetch();
    entered();
    await gate;
    await route.fulfill({ response }).catch(() => {}); // Browser may have aborted the superseded request.
    completed();
  });
  await page.goto(selectedDay);
  await page.getByRole("button", { name: "Reveal outcomes" }).click();
  await apply(page, "2026-01-14", "00:00");
  await started;
  await expect(page.getByRole("status")).toContainText(
    "Loading the selected decision",
  );
  await expect(page.locator(".card")).toHaveCount(0);
  await apply(page, "2026-01-31", "09:00");
  await expect(
    page.getByRole("heading", { name: "1 Feb 2026", exact: true }),
  ).toBeVisible();
  release();
  await oldResponseFinished;
  await expect(
    page.getByRole("heading", { name: "1 Feb 2026", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Decision date", { exact: true })).toHaveValue(
    "2026-01-31",
  );
  await expect(
    page.getByRole("button", { name: "Reveal outcomes" }),
  ).toBeVisible();
});

test("synthetic failures: retry recovers daily data while monthly failure stays explicit", async ({
  page,
}) => {
  let failDaily = true;
  await page.route("**/api/analysis?**", (route) =>
    failDaily
      ? route.fulfill({
          status: 503,
          json: { detail: "Analysis data is unavailable." },
        })
      : route.continue(),
  );
  await page.route("**/api/monthly-summary?**", (route) =>
    route.fulfill({
      status: 500,
      contentType: "text/plain",
      body: "Internal Server Error",
    }),
  );
  await page.goto(selectedDay);
  await expect(page.getByRole("alert")).toContainText(
    "Analysis data is unavailable",
  );
  await expect(page.locator(".card")).toHaveCount(0);
  failDaily = false;
  await page.getByRole("button", { name: "Retry requests" }).click();
  await page
    .getByRole("button", { name: "Accuracy view", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Forecast versus outcome" }),
  ).toContainText("782.8");
  await expect(page.locator(".monthly").getByRole("alert")).toContainText(
    "The analysis request failed",
  );
});

test("synthetic gaps: zero stays zero, an interior null breaks the line, and unmatched metrics stay unavailable", async ({
  page,
  request,
}) => {
  const response = await request.get(
    "/api/analysis?decision_date=2026-01-15&cutoff_time=09:00",
  );
  const data = await response.json();
  data.intervals[0].forecast_mw = 0;
  data.intervals[12].forecast_mw = null;
  data.intervals[12].forecast_published_at = null;
  for (const item of data.intervals) {
    item.actual_mw = null;
    item.error_mw = null;
  }
  Object.assign(data.coverage, {
    forecast_hours: 23,
    actual_hours: 0,
    matched_hours: 0,
    available_actual_half_hours: 0,
  });
  data.metrics = {
    sample_count: 0,
    mae_mw: null,
    bias_mw: null,
    rmse_mw: null,
  };
  data.largest_overforecasts = [];
  await page.route("**/api/analysis?**", (route) =>
    route.fulfill({ json: data }),
  );
  await page.goto(selectedDay);
  await expect(page.locator(".coverage-badge")).toContainText("23 / 24");
  const path = await page.locator(".recharts-line-curve").getAttribute("d");
  expect(path?.match(/M/g)).toHaveLength(2);
  await page.getByText("Hourly data · 24 intervals", { exact: true }).click();
  await expect(
    page.locator("details table tbody tr").first().locator("td").first(),
  ).toHaveText("0");
  await expect(page.locator("details table tbody tr").nth(12)).toContainText(
    "Unavailable",
  );
  await page.getByRole("button", { name: "Reveal outcomes" }).click();
  const accuracy = page.getByRole("region", {
    name: "Forecast versus outcome",
  });
  await expect(accuracy.locator(".metric strong")).toHaveText([
    "Unavailable MW",
    "Unavailable MW",
    "Unavailable MW",
  ]);
  await expect(accuracy).toContainText("No matched pairs");
});

test("real snapshot: narrow layouts keep controls and both views usable without page overflow", async ({
  page,
}, info) => {
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(selectedDay);
    await expect(
      page.getByRole("button", { name: "Reveal outcomes" }),
    ).toBeVisible();
    await expect(
      page.getByLabel("Decision date", { exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    await page
      .getByRole("button", { name: "Accuracy view", exact: true })
      .click();
    await page.getByText("Hourly data · 24 intervals", { exact: true }).click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: info.outputPath(`mobile-${width}.png`),
      fullPage: true,
    });
  }
});
