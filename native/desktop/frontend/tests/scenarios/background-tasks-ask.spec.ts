import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// Asking the agent for a background classification job from the Libro grid
// and the selection inspector, and reviewing what a job proposed: a proposal
// is applied only when the person accepts it, through the job's apply at the
// revision they saw, and each accepted proposal says whether it was applied
// or why not. The scenario host's jobs move only when a test moves them.

async function open(target: Page, jobs: string, extra = "") {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&jobs=${jobs}${extra}`,
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(grid(target).locator("[data-kind=data]").first()).toBeVisible();
}

const grid = (target: Page) => target.locator(".ledger-page").getByRole("grid");
const row = (target: Page, id: string) =>
  grid(target).locator(`[data-kind=data][data-key="${id}"]`);
const trigger = (target: Page) => target.locator(".background-tasks-trigger");
const panel = (target: Page) => target.locator("aside.ledger-panel");
const proposal = (target: Page) =>
  panel(target).locator(".ledger-job-proposal");

const jobId = (target: Page, shape: "progress" | "settled") =>
  target.evaluate((name) => window.__scenarioBackgroundTasks!.job(name), shape);
const movementsOf = (target: Page, job: string) =>
  target.evaluate((id) => window.__scenarioBackgroundTasks!.movements(id), job);
const requests = (target: Page, definition: string) =>
  target.evaluate(
    (name) => window.__scenarioLedger!.requests(name),
    definition,
  );
const LIST_READ = "ledger ledger.list";
const calls = (target: Page, call: string) =>
  target.evaluate(
    (prefix) =>
      (window.__scenarioHostCalls ?? []).filter((line) => line === prefix)
        .length,
    call,
  );

async function inspect(target: Page, id: string) {
  await row(target, id).locator("[data-column=status]").click();
  if (!(await panel(target).isVisible()))
    await target.keyboard.press("Alt+KeyI");
  await expect(panel(target).locator(".ledger-inspector")).toBeVisible();
}

const askItem = (target: Page) =>
  target.getByRole("menu").getByRole("menuitem", {
    name: label("desktop.background_tasks.ask_agent"),
  });

test("the row menu asks the agent about one movement, and the indicator and the row show the job", async ({
  page,
}) => {
  await open(page, "");
  const first = grid(page).locator("[data-kind=data]").first();
  const id = (await first.getAttribute("data-key"))!;
  await expect(trigger(page)).toHaveAttribute("data-active", "0");
  await first.locator("[data-column=description]").click({ button: "right" });
  await askItem(page).click();
  await expect(trigger(page)).toHaveAttribute("data-active", "1");
  expect(await requests(page, "ledger.classify.job.enqueue")).toEqual([
    { scope: "single", movement_ids: [id] },
  ]);
  const [job] = await page.evaluate(() =>
    window.__scenarioBackgroundTasks!.enqueued(),
  );
  // The new job is run at once, and the row shows it being classified.
  await expect
    .poll(() => page.evaluate(() => window.__scenarioBackgroundTasks!.runs()))
    .toEqual([job]);
  await expect(row(page, id).locator("[data-job-state]")).toHaveAttribute(
    "data-job-state",
    "classifying",
  );
  await expect(page.locator(".ledger-toast")).toContainText(
    label("desktop.background_tasks.outcome.enqueued"),
  );
});

test("the row menu says why a movement a job is classifying cannot be asked about again", async ({
  page,
}) => {
  await open(page, "progress");
  const job = await jobId(page, "progress");
  const movements = await movementsOf(page, job);
  const held = row(page, movements[2]!);
  await expect(held.locator("[data-job-state]")).toHaveAttribute(
    "data-job-state",
    "classifying",
  );
  await held.locator("[data-column=description]").click({ button: "right" });
  const item = askItem(page);
  await expect(item).toBeDisabled();
  await expect(item.locator("[data-description]")).toHaveText(
    label("desktop.background_tasks.ask_agent_held"),
  );
});

test("the selection inspector asks one job over every selected movement it can, beyond twenty", async ({
  page,
}) => {
  await open(page, "", "&ledgerRows=30");
  const rows = grid(page).locator("[data-kind=data]");
  await rows.first().locator("[data-column=description]").click();
  await page.keyboard.press("Control+KeyA");
  if (!(await panel(page).isVisible())) await page.keyboard.press("Alt+KeyI");
  const selection = panel(page).locator(".ledger-selection");
  await expect(selection).toBeVisible();
  const ask = selection.getByRole("button", {
    name: label("desktop.background_tasks.ask_agent"),
  });
  await ask.click();
  await expect(trigger(page)).toHaveAttribute("data-active", "1");
  const sent = await requests(page, "ledger.classify.job.enqueue");
  expect(sent).toHaveLength(1);
  expect(sent[0]!.scope).toBe("selection");
  const asked = sent[0]!.movement_ids as string[];
  expect(asked.length).toBeGreaterThan(20);
  expect(new Set(asked).size).toBe(asked.length);
  await expect(selection.locator("[data-notice=changed]")).toHaveText(
    label("desktop.background_tasks.outcome.enqueued"),
  );
  // Every one of them is now being classified: none is left to ask about,
  // and the inspector says why.
  await expect(ask).toBeDisabled();
  await expect(selection.locator("[data-ask-agent-none]")).toHaveText(
    label("desktop.background_tasks.ask_agent_none"),
  );
});

test("a proposed movement shows its proposal, and accepting it applies it and reads the window again", async ({
  page,
}) => {
  await open(page, "settled");
  const job = await jobId(page, "settled");
  const [movement] = await movementsOf(page, job);
  await expect(
    row(page, movement!).locator("[data-job-state=proposed]"),
  ).toBeVisible();
  await inspect(page, movement!);
  const shown = proposal(page);
  await expect(shown.locator("[data-proposed=category_id]")).toHaveText(
    label("desktop.ledger.category.gastos_bancarios"),
  );
  await expect(shown.locator("[data-proposed=iva_category]")).toHaveText(
    label("desktop.ledger.iva_category.domestic_general"),
  );
  await expect(shown.locator("[data-lane]")).toHaveText(
    label("desktop.background_tasks.proposal.read_by", {
      model: "fixture-small",
    }),
  );
  const before = await calls(page, LIST_READ);
  await shown.locator("[data-proposal-action=accept]").click();
  await expect(shown.locator("[data-apply-result=applied]")).toHaveText(
    label("desktop.background_tasks.proposal.item_applied"),
  );
  const sent = await requests(page, "ledger.classify.job.apply");
  expect(sent).toHaveLength(1);
  expect(sent[0]).toMatchObject({
    job_id: job,
    expected_revision: 3,
    accepted: [{ movement_id: movement }],
  });
  // The job's newer revision applied a movement of the window: the rows
  // are read again, and the movement no longer shows a proposal.
  await expect.poll(() => calls(page, LIST_READ)).toBeGreaterThan(before);
  await expect(
    row(page, movement!).locator("[data-job-state=proposed]"),
  ).toHaveCount(0);
});

test("an accepted proposal the ledger refuses says why", async ({ page }) => {
  await open(page, "settled");
  const job = await jobId(page, "settled");
  const movements = await movementsOf(page, job);
  const movement = movements[1]!;
  await page.evaluate(
    (id) =>
      window.__scenarioBackgroundTasks!.refuseApply(id, "category_unavailable"),
    movement,
  );
  await inspect(page, movement);
  await proposal(page).locator("[data-proposal-action=accept]").click();
  await expect(
    proposal(page).locator("[data-apply-refusal=category_unavailable]"),
  ).toHaveText(
    label("desktop.background_tasks.proposal.item_refused", {
      cause: label(
        "desktop.background_tasks.apply_refusal.category_unavailable",
      ),
    }),
  );
  // The proposal stays for the person to classify by hand or discard.
  await proposal(page).locator("[data-proposal-action=discard]").click();
  await expect(proposal(page).locator("[data-proposal-discarded]")).toHaveText(
    label("desktop.background_tasks.proposal.discarded"),
  );
});

test("the selection inspector applies the proposals the person marked, in one apply", async ({
  page,
}) => {
  await open(page, "settled");
  const job = await jobId(page, "settled");
  const movements = await movementsOf(page, job);
  await row(page, movements[0]!).locator("[data-column=status]").click();
  await row(page, movements[1]!)
    .locator("[data-column=status]")
    .click({ modifiers: ["Control"] });
  if (!(await panel(page).isVisible())) await page.keyboard.press("Alt+KeyI");
  const listed = panel(page).locator(".ledger-job-proposals");
  await expect(listed).toContainText(
    label("desktop.background_tasks.proposal.list", { count: 2 }),
  );
  const apply = listed.locator("[data-proposal-action=apply_marked]");
  await expect(apply).toBeDisabled();
  for (const id of movements)
    await listed.locator(`li[data-movement="${id}"] input`).check();
  await apply.click();
  await expect(listed.locator("[data-apply-result=applied]")).toHaveCount(2);
  const sent = await requests(page, "ledger.classify.job.apply");
  expect(sent).toHaveLength(1);
  expect(
    (sent[0]!.accepted as { movement_id: string }[]).map(
      (entry) => entry.movement_id,
    ),
  ).toEqual(movements);
});
