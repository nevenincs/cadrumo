import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The window's background tasks over the scenario host's classification
// jobs: the title-bar indicator and its panel, the revision-gated reads a
// cue, a subscription and a regained focus make, the run a subscription
// resumes, the actions on a job and what each came to, and the state a
// Ledger row shows of the job that holds it. The jobs move only when a test
// moves them, so anything read without a move would be a read on a timer.

async function open(target: Page, jobs: string) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&jobs=${jobs}`,
  );
}

const trigger = (target: Page) => target.locator(".background-tasks-trigger");
const panel = (target: Page) => target.locator(".background-tasks-panel");
const jobId = (target: Page, shape: string) =>
  target.evaluate(
    (name) =>
      window.__scenarioBackgroundTasks!.job(
        name as "progress" | "consent" | "resume" | "settled",
      ),
    shape,
  );
const entry = (target: Page, job: string) =>
  panel(target).locator(`[data-job="${job}"]`);

/** How many host calls so far start with `call`. */
const calls = (target: Page, call: string) =>
  target.evaluate(
    (prefix) =>
      (window.__scenarioHostCalls ?? []).filter((line) => line === prefix)
        .length,
    call,
  );
const JOB_READ = "ledger ledger.classify.job.read";
const LIST_READ = "ledger ledger.list";

async function openPanel(target: Page) {
  await trigger(target).click();
  await expect(panel(target)).toBeVisible();
}

/** Waits until the reads a subscription and its resumed run made are in. */
async function settled(target: Page, job: string) {
  await expect(entry(target, job)).toBeVisible();
  await expect
    .poll(() => target.evaluate(() => window.__scenarioBackgroundTasks!.runs()))
    .toContain(job);
  await expect(entry(target, job)).toHaveAttribute("data-status", "running");
}

test("the indicator counts the jobs in progress and shows a job's progress and a failure by its cause", async ({
  page,
}) => {
  await open(page, "progress");
  const job = await jobId(page, "progress");
  await expect(trigger(page)).toHaveAttribute("data-active", "1");
  await openPanel(page);
  const shown = entry(page, job);
  await expect(shown.locator("[data-count=progress]")).toHaveText(
    label("desktop.background_tasks.progress", { done: 3, total: 6 }),
  );
  await expect(shown.locator("[data-count=proposed]")).toHaveText(
    label("desktop.background_tasks.proposed", { count: 2 }),
  );
  await expect(shown.locator("[data-cause=model_unavailable]")).toHaveText(
    label("desktop.background_tasks.failure_group", {
      cause: label("desktop.background_tasks.cause.model_unavailable"),
      count: 1,
    }),
  );
  // A job still running is cancelled, not retried or dismissed.
  await expect(shown.locator("[data-action=cancel]")).toBeVisible();
  await expect(shown.locator("[data-action=retry]")).toHaveCount(0);
  await expect(shown.locator("[data-action=dismiss]")).toHaveCount(0);
});

test("with no job the panel says there is none", async ({ page }) => {
  await open(page, "");
  await expect(trigger(page)).toHaveAttribute("data-active", "0");
  await openPanel(page);
  await expect(panel(page)).toContainText(
    label("desktop.background_tasks.empty"),
  );
});

test("a cue changes the view only for a newer revision of the profile's job, and nothing is read on a timer", async ({
  page,
}) => {
  await open(page, "progress");
  const job = await jobId(page, "progress");
  await openPanel(page);
  await settled(page, job);
  const progress = entry(page, job).locator("[data-count=progress]");
  await expect(progress).toHaveText(
    label("desktop.background_tasks.progress", { done: 3, total: 6 }),
  );
  const before = await calls(page, JOB_READ);

  // The revision the window holds, and another profile's: nothing is read.
  await page.evaluate((id) => {
    const tasks = window.__scenarioBackgroundTasks!;
    tasks.cue(id);
    tasks.cue(id, 1);
    tasks.cueOtherProfile(id);
  }, job);
  await page.waitForTimeout(500);
  expect(await calls(page, JOB_READ)).toBe(before);

  // A newer revision is read once, and the view follows it.
  await page.evaluate((id) => window.__scenarioBackgroundTasks!.step(id), job);
  await expect(progress).toHaveText(
    label("desktop.background_tasks.progress", { done: 4, total: 6 }),
  );
  expect(await calls(page, JOB_READ)).toBe(before + 1);

  // Left alone, the window reads nothing more.
  await page.waitForTimeout(1500);
  expect(await calls(page, JOB_READ)).toBe(before + 1);
});

test("a regained focus reads a change no cue carried", async ({ page }) => {
  await open(page, "progress");
  const job = await jobId(page, "progress");
  await openPanel(page);
  await settled(page, job);
  const progress = entry(page, job).locator("[data-count=progress]");
  await page.evaluate(
    (id) => window.__scenarioBackgroundTasks!.step(id, { silently: true }),
    job,
  );
  await page.waitForTimeout(300);
  await expect(progress).toHaveText(
    label("desktop.background_tasks.progress", { done: 3, total: 6 }),
  );
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(progress).toHaveText(
    label("desktop.background_tasks.progress", { done: 4, total: 6 }),
  );
});

test("subscribing runs again a job left with movements to ask, and says so", async ({
  page,
}) => {
  await open(page, "resume,settled");
  const resumed = await jobId(page, "resume");
  const done = await jobId(page, "settled");
  await expect
    .poll(() => page.evaluate(() => window.__scenarioBackgroundTasks!.runs()))
    .toEqual([resumed]);
  await openPanel(page);
  await expect(
    entry(page, resumed).locator("[data-notice=resuming]"),
  ).toHaveText(label("desktop.background_tasks.resuming"));
  // A settled job is not run again.
  await expect(entry(page, done)).toBeVisible();
  await expect(entry(page, done).locator("[data-notice]")).toHaveCount(0);
  // When the resumed run ends, the window no longer says it resumes.
  await page.evaluate(
    (id) => window.__scenarioBackgroundTasks!.finish(id),
    resumed,
  );
  await expect(entry(page, resumed)).toHaveAttribute("data-status", "settled");
  await expect(entry(page, resumed).locator("[data-notice]")).toHaveCount(0);
});

test("cancelling a running job says the movement being asked finishes first", async ({
  page,
}) => {
  await open(page, "progress");
  const job = await jobId(page, "progress");
  await openPanel(page);
  await settled(page, job);
  await entry(page, job).locator("[data-action=cancel]").click();
  await expect(entry(page, job).locator("[data-notice=changed]")).toHaveText(
    label("desktop.background_tasks.outcome.cancelling"),
  );
  await expect(entry(page, job)).toHaveAttribute("data-status", "cancelling");
  const sent = await page.evaluate(() =>
    window.__scenarioLedger!.requests("ledger.classify.job.cancel"),
  );
  expect(sent).toEqual([{ job_id: job, expected_revision: 4 }]);
});

test("an action on a job that changed unseen shows the served refusal and reads the job again", async ({
  page,
}) => {
  await open(page, "progress");
  const job = await jobId(page, "progress");
  await openPanel(page);
  await settled(page, job);
  await page.evaluate(
    (id) => window.__scenarioBackgroundTasks!.step(id, { silently: true }),
    job,
  );
  await entry(page, job).locator("[data-action=cancel]").click();
  await expect(entry(page, job).locator("[data-notice=refused]")).toContainText(
    "The job changed since you read it",
  );
  await expect(entry(page, job).locator("[data-count=progress]")).toHaveText(
    label("desktop.background_tasks.progress", { done: 4, total: 6 }),
  );
});

test("asking again for the failed movements retries them and runs the job", async ({
  page,
}) => {
  await open(page, "consent");
  const job = await jobId(page, "consent");
  await openPanel(page);
  await entry(page, job).locator("[data-action=retry]").click();
  await expect(entry(page, job).locator("[data-notice=changed]")).toHaveText(
    label("desktop.background_tasks.outcome.retried"),
  );
  await expect
    .poll(() => page.evaluate(() => window.__scenarioBackgroundTasks!.runs()))
    .toEqual([job]);
  await expect(entry(page, job)).toHaveAttribute("data-status", "running");
});

test("dismissing a settled job puts it away and says its proposals were not applied", async ({
  page,
}) => {
  await open(page, "settled");
  const job = await jobId(page, "settled");
  await openPanel(page);
  await entry(page, job).locator("[data-action=dismiss]").click();
  await expect(entry(page, job)).toHaveCount(0);
  await expect(panel(page).locator("[data-notice=dismissed]")).toHaveText(
    label("desktop.background_tasks.outcome.dismissed"),
  );
  await expect(panel(page)).toContainText(
    label("desktop.background_tasks.empty"),
  );
});

test("a consent failure offers to authorise the job's lane for the time chosen, or a local model", async ({
  page,
}) => {
  await open(page, "consent");
  const job = await jobId(page, "consent");
  await openPanel(page);
  const shown = entry(page, job);
  await expect(shown.locator("[data-cause=consent_required]")).toHaveText(
    label("desktop.background_tasks.failure_group", {
      cause: label("desktop.background_tasks.cause.consent_required"),
      count: 2,
    }),
  );
  await expect(
    shown.locator(".ledger-consent-switch_to_local_lane"),
  ).toHaveText(label("desktop.background_tasks.switch_local"));
  await shown.locator(".ledger-consent-authorise_off_host").click();
  await shown
    .getByRole("group", {
      name: label("desktop.background_tasks.consent_scope_prompt"),
    })
    .getByRole("button", {
      name: label("desktop.background_tasks.consent_scope.once"),
    })
    .click();
  await expect(shown.locator("[data-notice=changed]")).toHaveText(
    label("desktop.background_tasks.outcome.authorised"),
  );
  const sent = await page.evaluate(() =>
    window.__scenarioLedger!.requests("ledger.classify.job.authorise"),
  );
  expect(sent).toEqual([
    {
      job_id: job,
      expected_revision: 3,
      consent: {
        scope: "once",
        provider_id: "fixture-cloud",
        connection: "api",
        model: "fixture-large",
      },
    },
  ]);
  await expect
    .poll(() => page.evaluate(() => window.__scenarioBackgroundTasks!.runs()))
    .toEqual([job]);
});

test.describe("the Libro grid", () => {
  const grid = (target: Page) =>
    target.locator(".ledger-page").getByRole("grid");
  const row = (target: Page, id: string) =>
    grid(target).locator(`[data-kind=data][data-key="${id}"]`);

  async function openLedger(target: Page) {
    await target.locator("[data-rail=ledger]").click();
    await expect(grid(target)).toBeVisible();
  }

  test("each movement shows whether it is being classified, has a proposal or failed, and why", async ({
    page,
  }) => {
    await open(page, "progress");
    const job = await jobId(page, "progress");
    const movements = await page.evaluate(
      (id) => window.__scenarioBackgroundTasks!.movements(id),
      job,
    );
    await openLedger(page);
    await expect(
      row(page, movements[0]!).locator("[data-job-state=proposed]"),
    ).toBeVisible();
    const asked = row(page, movements[2]!).locator("[data-job-state]");
    await expect(asked).toHaveAttribute("data-job-state", "classifying");
    const failed = row(page, movements[5]!).locator("[data-job-state=failed]");
    await expect(failed).toHaveAttribute("data-job-cause", "model_unavailable");
    await failed.hover();
    await expect(page.getByRole("tooltip")).toContainText(
      label("desktop.background_tasks.row.failed", {
        cause: label("desktop.background_tasks.cause.model_unavailable"),
      }),
    );
    // A movement asked moves on with the job's next revision.
    await page.evaluate(
      (id) => window.__scenarioBackgroundTasks!.step(id),
      job,
    );
    await expect(asked).toHaveAttribute("data-job-state", "proposed");
  });

  test("a job that applies a movement of the window reads the window again, once per newer revision", async ({
    page,
  }) => {
    await open(page, "progress");
    const job = await jobId(page, "progress");
    await openLedger(page);
    await openPanel(page);
    await settled(page, job);
    await page.keyboard.press("Escape");
    const movements = await page.evaluate(
      (id) => window.__scenarioBackgroundTasks!.movements(id),
      job,
    );
    await expect(
      row(page, movements[0]!).locator("[data-job-state=proposed]"),
    ).toBeVisible();
    const before = await calls(page, LIST_READ);
    // Progress that changes no ledger fact reads no rows.
    await page.evaluate(
      (id) => window.__scenarioBackgroundTasks!.step(id),
      job,
    );
    await expect(
      row(page, movements[2]!).locator("[data-job-state=proposed]"),
    ).toBeVisible();
    expect(await calls(page, LIST_READ)).toBe(before);
    // Applied proposals changed the ledger: the window is read again.
    await page.evaluate(
      (id) => window.__scenarioBackgroundTasks!.apply(id),
      job,
    );
    await expect.poll(() => calls(page, LIST_READ)).toBeGreaterThan(before);
    const after = await calls(page, LIST_READ);
    // The same revision cued again reads nothing.
    await page.evaluate((id) => window.__scenarioBackgroundTasks!.cue(id), job);
    await page.waitForTimeout(500);
    expect(await calls(page, LIST_READ)).toBe(after);
  });
});
