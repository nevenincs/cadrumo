import { expect, test, type Page } from "@playwright/test";
import { moreViewsButton, openRailView } from "../support/railViews";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { agentTurns, ask, settled } from "../support/agent";
import { windowToast } from "../support/toast";
import { open, startFromDocs } from "../support/scenarioShell";

// Operations is a page of the first pane that lists the runs of the signed-in
// profile's operation journal and draws what the read served and nothing
// else. It reads when it opens and when the person asks, and each standing is
// kept apart. It never runs, retries or cancels anything.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

const railButton = moreViewsButton;
const operationsPage = (target: Page) => target.locator(".operations-page");
const runs = (target: Page) =>
  operationsPage(target).locator("[data-operation-run]");
const run = (target: Page, id: string) =>
  operationsPage(target).locator(`[data-operation-run="${id}"]`);
const reads = (target: Page) =>
  target.evaluate(
    () =>
      (window.__scenarioHostCalls ?? []).filter((call) =>
        call.startsWith("operations "),
      ).length,
  );
const wait = (target: Page, ms: number) =>
  target.evaluate(
    (delay) => new Promise((resolve) => window.setTimeout(resolve, delay)),
    ms,
  );

test("the page opens from the rail, reads once, and lists the runs newest first", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  await expect(railButton(target)).toHaveAttribute("aria-pressed", "true");
  await expect(target.locator("#tab-docs")).toHaveText(
    label("desktop.operations.title"),
  );
  const page = operationsPage(target);
  await expect(page).toBeVisible();
  await expect(page).toBeFocused();
  await expect(page.locator("[data-operations-orientation]")).toHaveText(
    label("desktop.operations.orientation"),
  );
  // One page of 25 of the 30 runs, in the order the product served them.
  await expect(runs(target)).toHaveCount(25);
  await expect(runs(target).first()).toHaveAttribute(
    "data-operation-run",
    "synthetic-run-00",
  );
  await expect(runs(target).nth(1)).toHaveAttribute(
    "data-operation-run",
    "synthetic-run-01",
  );
  await expect(page.locator("[data-operations-count]")).toHaveText(
    label("desktop.operations.count", { shown: 25, total: 30 }),
  );
  await expect(
    target.evaluate(() => window.__scenarioHostCalls ?? []),
  ).resolves.toContain("operations 25 -");
  // Nothing polls.
  await wait(target, 600);
  expect(await reads(target)).toBe(1);
});

test("a run shows its definition as the protocol token it is, with generic words for its states", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  const succeeded = run(target, "synthetic-run-02");
  await expect(succeeded.locator("[data-operation-definition]")).toHaveText(
    "ledger.classify.bulk",
  );
  await expect(succeeded.locator("[data-operation-definition]")).toHaveCSS(
    "font-family",
    /mono/i,
  );
  await expect(succeeded.locator("[data-operation-lifecycle]")).toHaveText(
    label("desktop.operations.lifecycle.terminal"),
  );
  await expect(succeeded.locator("[data-operation-effect]")).toHaveText(
    `${label("desktop.operations.field_effect")}: ${label("desktop.operations.effect.updated")}`,
  );
  const receipt = succeeded.locator("[data-operation-receipt]");
  await expect(receipt).toHaveAttribute("data-operation-receipt", "succeeded");
  await expect(receipt).toContainText(
    `${label("desktop.operations.field_outcome")}: ${label("desktop.operations.outcome.succeeded")}`,
  );
  await expect(receipt).toContainText(
    label("desktop.operations.result_stored"),
  );
  // A refused and a failed run keep their own outcome, reference and code.
  const refused = run(target, "synthetic-run-04");
  await expect(refused.locator("[data-operation-refusal]")).toHaveText(
    label("desktop.operations.refusal_ref", { ref: "synthetic-refusal-ref" }),
  );
  await expect(refused.locator("[data-operation-receipt]")).toContainText(
    label("desktop.operations.outcome.refused"),
  );
  const failed = run(target, "synthetic-run-03");
  await expect(failed.locator("[data-operation-error]")).toHaveText(
    label("desktop.operations.error_code", { code: "SYNTHETIC_FAILURE" }),
  );
  await expect(failed.locator("[data-operation-receipt]")).toContainText(
    label("desktop.operations.result_not_stored"),
  );
});

test("a settling run and an unknown effect are said as such, and a run still going has no receipt", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  const settling = run(target, "synthetic-run-00");
  await expect(settling).toHaveAttribute("data-lifecycle", "settling");
  await expect(settling).toHaveAttribute("data-effect", "unknown");
  await expect(settling.locator("[data-operation-lifecycle]")).toHaveText(
    label("desktop.operations.lifecycle.settling"),
  );
  await expect(settling.locator("[data-operation-effect]")).toHaveText(
    `${label("desktop.operations.field_effect")}: ${label("desktop.operations.effect.unknown")}`,
  );
  await expect(settling.locator("[data-operation-receipt]")).toHaveCount(0);
  // An unknown effect after a time-out is not folded into a failure or a success.
  const timedOut = run(target, "synthetic-run-05");
  await expect(timedOut.locator("[data-operation-effect]")).toContainText(
    label("desktop.operations.effect.unknown"),
  );
  await expect(timedOut.locator("[data-operation-receipt]")).toContainText(
    label("desktop.operations.outcome.timed_out"),
  );
  const running = run(target, "synthetic-run-01");
  await expect(running.locator("[data-operation-lifecycle]")).toHaveText(
    label("desktop.operations.lifecycle.running"),
  );
  await expect(running.locator("[data-operation-phase]")).toHaveText(
    label("desktop.operations.phase", { phase: "overview.status" }),
  );
  await expect(running.locator("[data-operation-receipt]")).toHaveCount(0);
  const cancelling = run(target, "synthetic-run-06");
  await expect(cancelling.locator("[data-operation-cancellation]")).toHaveText(
    label("desktop.operations.cancellation_requested"),
  );
});

test("a run's page is the register's label and opens the page as a link does", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  const link = run(target, "synthetic-run-02").locator(
    '[data-operation-page="ledger"]',
  );
  await expect(link).toHaveText(label("navigation.view.ledger.label"));
  await link.click();
  await expect(target.locator(".ledger-page")).toBeVisible();
  await expect(operationsPage(target)).toHaveCount(0);
});

test("a page the window does not draw is named by its label and cannot be opened", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  const undrawn = run(target, "synthetic-run-08");
  await expect(undrawn.locator("[data-operation-page-label]")).toHaveText(
    label("navigation.view.installation.label"),
  );
  await expect(undrawn.getByRole("button")).toHaveCount(0);
  // A run with no page says nothing of one.
  await expect(
    run(target, "synthetic-run-07").locator("[data-operation-page]"),
  ).toHaveCount(0);
});

test("more runs are read only when asked, after the continuation the page served", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  await expect(runs(target)).toHaveCount(25);
  expect(await reads(target)).toBe(1);
  await operationsPage(target)
    .getByRole("button", { name: label("desktop.operations.show_more") })
    .click();
  await expect(runs(target)).toHaveCount(30);
  await expect(
    target.evaluate(() => window.__scenarioHostCalls ?? []),
  ).resolves.toContain("operations 25 synthetic-run-24");
  await expect(
    operationsPage(target).locator("[data-operations-count]"),
  ).toHaveText(label("desktop.operations.count", { shown: 30, total: 30 }));
  // The last page serves no continuation, so there is nothing more to ask.
  await expect(
    operationsPage(target).getByRole("button", {
      name: label("desktop.operations.show_more"),
    }),
  ).toHaveCount(0);
  expect(await reads(target)).toBe(2);
});

test("a request for more that fails says so by its code and leaves the list standing", async ({
  page: target,
}) => {
  await seedLayout(target);
  await target.addInitScript(() => {
    window.__scenarioOperationsMoreRefused = true;
  });
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  await operationsPage(target)
    .getByRole("button", { name: label("desktop.operations.show_more") })
    .click();
  const failed = operationsPage(target).locator(
    "[data-operations-more-failed]",
  );
  await expect(failed).toHaveAttribute(
    "data-operations-more-failed",
    "timed_out",
  );
  await expect(failed).toContainText(
    label("desktop.operations.more_failed", { code: "timed_out" }),
  );
  await expect(runs(target)).toHaveCount(25);
  expect(await reads(target)).toBe(2);
  // Left alone it is not asked again; asked again once the host answers, it lists the rest.
  await wait(target, 600);
  expect(await reads(target)).toBe(2);
  await target.evaluate(() => {
    window.__scenarioOperationsMoreRefused = false;
  });
  await operationsPage(target)
    .getByRole("button", { name: label("desktop.operations.read_again") })
    .click();
  await expect(runs(target)).toHaveCount(30);
});

test("a history with no runs says so, and is not the standing of a read that failed", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "empty");
  await openRailView(target, "desktop.operations.title");
  const page = operationsPage(target);
  await expect(page.locator("[data-operations-empty]")).toHaveText(
    label("desktop.operations.empty"),
  );
  await expect(page.locator("[data-operations-failed]")).toHaveCount(0);
  await expect(runs(target)).toHaveCount(0);
  await expect(page.locator("[data-operations-unreadable]")).toHaveCount(0);
});

test("a read in flight is told apart from the others", async ({
  page: target,
}) => {
  await seedLayout(target);
  await target.addInitScript(() => {
    window.__scenarioOperationsHeld = true;
  });
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  const page = operationsPage(target);
  await expect(page.getByRole("status")).toHaveText(
    label("desktop.operations.loading"),
  );
  await expect(page.locator("[data-operations-empty]")).toHaveCount(0);
  await expect(runs(target)).toHaveCount(0);
  await target.evaluate(() => {
    window.__scenarioOperationsHeld = false;
  });
  await expect(runs(target)).toHaveCount(25);
});

test("a read that fails says so with its code, is never drawn as no runs and is read again only on request", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "views-refused");
  await openRailView(target, "desktop.operations.title");
  const failed = operationsPage(target).locator("[data-operations-failed]");
  await expect(failed).toHaveAttribute("data-operations-failed", "timed_out");
  await expect(failed).toHaveText(
    label("desktop.operations.failed", { code: "timed_out" }),
  );
  await expect(
    operationsPage(target).locator("[data-operations-empty]"),
  ).toHaveCount(0);
  expect(await reads(target)).toBe(1);
  await wait(target, 600);
  expect(await reads(target)).toBe(1);
});

test("a read that fails is read again on request and then shows the runs", async ({
  page: target,
}) => {
  await seedLayout(target);
  await target.addInitScript(() => {
    window.__scenarioOperationsRefused = true;
  });
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  await expect(
    operationsPage(target).locator("[data-operations-failed]"),
  ).toBeVisible();
  await target.evaluate(() => {
    window.__scenarioOperationsRefused = false;
  });
  await operationsPage(target)
    .getByRole("button", { name: label("desktop.operations.read_again") })
    .click();
  await expect(runs(target)).toHaveCount(25);
  expect(await reads(target)).toBe(2);
});

test("records the journal could not read or attribute are counted and never hidden", async ({
  page: target,
}) => {
  await seedLayout(target);
  await target.addInitScript(() => {
    window.__scenarioOperationsDamaged = true;
  });
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  const page = operationsPage(target);
  await expect(page.locator("[data-operations-unreadable]")).toHaveText(
    label("desktop.operations.unreadable", { count: 2 }),
  );
  await expect(page.locator("[data-operations-unverifiable]")).toHaveText(
    label("desktop.operations.unverifiable", { count: 1 }),
  );
  await expect(runs(target)).toHaveCount(25);
});

test("a run with a value the window has no word for refuses the read", async ({
  page: target,
}) => {
  await seedLayout(target);
  await target.addInitScript(() => {
    window.__scenarioOperationsUnrecognised = true;
  });
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  await expect(
    operationsPage(target).locator("[data-operations-failed]"),
  ).toHaveAttribute("data-operations-failed", "unavailable");
  await expect(runs(target)).toHaveCount(0);
});

test("refresh reads the history again, and only when asked", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  await expect(runs(target)).toHaveCount(25);
  expect(await reads(target)).toBe(1);
  await operationsPage(target)
    .getByRole("button", { name: label("desktop.operations.refresh") })
    .click();
  await expect.poll(() => reads(target)).toBe(2);
  await expect(runs(target)).toHaveCount(25);
});

test("the palette opens Operations by its label", async ({ page: target }) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await target.keyboard.press("ControlOrMeta+Shift+KeyK");
  const input = target
    .locator(".palette")
    .getByRole("combobox", { name: label("desktop.palette.label") });
  await expect(input).toBeFocused();
  await input.fill(label("navigation.view.operations.label"));
  await target
    .locator(".palette")
    .getByRole("option")
    .filter({
      has: target.locator(".palette-title", {
        hasText: new RegExp(`^${label("navigation.view.operations.label")}$`),
      }),
    })
    .click();
  await expect(operationsPage(target)).toBeVisible();
  await expect(operationsPage(target)).toBeFocused();
});

test("an agent link to Operations opens it with the keyboard on it and no notice", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await ask(target, "Respóndeme con enlaces");
  await settled(target);
  await agentTurns(target)
    .getByRole("link", { name: "las operaciones", exact: true })
    .click();
  const page = operationsPage(target);
  await expect(page).toBeVisible();
  await expect(page).toBeFocused();
  await expect(windowToast(target)).toHaveText("");
});

test("signing out drops the history and asks for a sign-in, reading nothing more", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.operations.title");
  await expect(runs(target)).toHaveCount(25);
  await target.keyboard.press("ControlOrMeta+k");
  await target
    .locator(".palette")
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.account.sign_out"));
  await target.keyboard.press("Enter");
  const page = operationsPage(target);
  await expect(page).toContainText(label("desktop.operations.signed_out"));
  await expect(runs(target)).toHaveCount(0);
  await expect(page.locator("[data-operations-orientation]")).toHaveCount(0);
  expect(await reads(target)).toBe(1);
});
