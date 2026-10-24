import { expect, test, type Locator, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The Ledger page's one write pause over the scenario's ledger: a write
// whose outcome was not seen holds every write on the page, in any
// section, until the person re-reads; a saved write whose answer was lost
// is said as saved; the review of a permanent link holds a link whose
// invoice it could not read, and asks a second tick for one in another
// currency; and the movements a finalized declaration seals are counted
// as skipped.

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const head = (target: Page) => target.locator(".pane-docs .pane-head");
const banner = (target: Page) =>
  page(target).locator(".ledger-paused [role=alert]");
const findings = (target: Page) => page(target).locator(".ledger-findings");
const review = (target: Page) => target.locator(".ledger-review");
const panel = (target: Page) => target.locator("aside.ledger-panel");
const body = (target: Page) => panel(target).locator(".ledger-inspector-body");
const editor = (target: Page) => target.locator(".ledger-invoice-editor");

const RULES = "desktop.ledger.rules.title";

const ledgerControls = {
  nextWrites: (
    target: Page,
    outcomes: ("unknown" | "saved_unread" | "refused")[],
  ) =>
    target.evaluate(
      (next) => window.__scenarioLedger!.nextWrites(next),
      outcomes,
    ),
  nextReads: (target: Page, definition: string, count: number) =>
    target.evaluate(
      ([name, times]) =>
        window.__scenarioLedger!.nextReads(name as string, times as number),
      [definition, count] as const,
    ),
};

async function openLedger(target: Page) {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(dataRows(target).first()).toBeVisible();
}

async function openRules(target: Page) {
  await head(target).locator(".ledger-setup").click();
  await target
    .getByRole("menuitem", { name: label("desktop.ledger.section.rules") })
    .click();
  await expect(target.locator(".ledger-setup-rules")).toBeVisible();
  await expect(target.getByRole("menu")).toHaveCount(0);
}

/** The Move up control of the last rule; its name gains the reason while
 * writes are paused. */
const moveUp = (target: Page) =>
  target
    .locator(".ledger-rules-table tbody tr")
    .nth(2)
    .getByRole("button", {
      name: new RegExp(
        `^${escape(label("desktop.ledger.rules.move_up", { rule: "" }))}`,
      ),
    });
const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const rowOf = (target: Page, text: string) =>
  dataRows(target)
    .filter({
      has: target.locator("[data-column=description]", { hasText: text }),
    })
    .first();
const cellOf = (row: Locator, column: string) =>
  row.locator(`[data-column=${column}]`);

async function typeInto(target: Page, cell: Locator, text: string) {
  await cell.click();
  await target.keyboard.press("Enter");
  const input = target.locator(".ledger-cell-editor");
  await expect(input).toBeVisible();
  await input.fill(text);
  await target.keyboard.press("Enter");
}

async function inspect(target: Page, text: string) {
  await cellOf(rowOf(target, text), "status").click();
  if (!(await panel(target).isVisible()))
    await target.keyboard.press("Alt+KeyI");
  await expect(panel(target).locator(".ledger-inspector h2")).toContainText(
    text,
  );
}

/** Stages a permanent link from `movement` to the invoice numbered
 * `invoice`, through the inspector's picker. */
async function stageLink(target: Page, movement: string, invoice: string) {
  await inspect(target, movement);
  const section = body(target).locator("[data-section-body=invoice]");
  await section.scrollIntoViewIfNeeded();
  await section
    .getByRole("button", {
      name: label("desktop.ledger.inspector.invoice.pick"),
    })
    .click();
  const list = target.locator("[data-slot=combobox]");
  await expect(list).toBeVisible();
  await target.keyboard.type(invoice);
  await list.getByRole("option", { name: invoice }).first().click();
  await expect(section).toContainText(
    label("desktop.ledger.inspector.invoice.staged", { invoice }),
  );
}

async function openReview(target: Page) {
  await target.locator(".ledger-tray-review").click();
  await expect(review(target)).toBeVisible();
  await expect(review(target).locator(".ledger-review-summary")).not.toHaveText(
    label("desktop.ledger.apply.reading"),
  );
}

test("a Setup write with an unknown outcome holds its form, and pressing it again sends nothing", async ({
  page: target,
}) => {
  await openLedger(target);
  await openRules(target);
  // The second answer would refuse a write sent again: none is.
  await ledgerControls.nextWrites(target, ["unknown", "refused"]);
  await moveUp(target).click();
  await expect(banner(target)).toContainText(
    `${label("desktop.ledger.paused.title")} · ${label(RULES)}`,
  );
  await expect(target.locator(".setup-call-line")).toContainText(
    label("desktop.ledger.form.unknown"),
  );
  const held = moveUp(target);
  await expect(held).toHaveAttribute("aria-disabled", "true");
  await expect(held).toHaveAccessibleName(
    new RegExp(escape(label("desktop.ledger.tray.paused_reason"))),
  );
  // Pressed anyway, it sends nothing.
  await held.click({ force: true });
  await expect(target.locator(".setup-call-line")).not.toContainText(
    label("desktop.ledger.form.refused", { code: "precondition_failed" }),
  );
  await expect(banner(target)).toBeVisible();
  // The re-read settles it, and writes may run again.
  await banner(target).locator(".ledger-paused-reread").click();
  await expect(findings(target)).toContainText(
    label("desktop.ledger.paused.read_again", { movement: label(RULES) }),
  );
  await expect(banner(target)).toHaveCount(0);
  await expect(target.locator(".setup-call-line")).toHaveCount(0);
  await expect(moveUp(target)).not.toHaveAttribute("aria-disabled", "true");
});

test("asking the model waits while writes are paused, as every other writer does", async ({
  page: target,
}) => {
  await openLedger(target);
  await openRules(target);
  await ledgerControls.nextWrites(target, ["unknown"]);
  await moveUp(target).click();
  await expect(banner(target)).toBeVisible();
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.movements") })
    .click();
  await expect(dataRows(target).first()).toBeVisible();
  await inspect(target, "PAPELERIA TRAZO");
  const ask = body(target).getByRole("button", {
    name: label("desktop.ledger.inspector.model.ask"),
    exact: true,
  });
  await expect(ask).toHaveAttribute("aria-disabled", "true");
  await expect(ask).toHaveAccessibleDescription(
    label("desktop.ledger.tray.paused_reason"),
  );
  // Pressed anyway, it asks nothing.
  await ask.click({ force: true });
  await expect(body(target).locator(".ledger-model [role=status]")).toHaveCount(
    0,
  );
  await expect(body(target).locator(".ledger-suggestion")).toHaveCount(0);
});

test("a saved write whose answer was not read is said as saved, never as failed", async ({
  page: target,
}) => {
  await openLedger(target);
  await openRules(target);
  await ledgerControls.nextWrites(target, ["saved_unread"]);
  await moveUp(target).click();
  await expect(banner(target)).toContainText(
    `${label("desktop.ledger.paused.saved_unread")} · ${label(RULES)}`,
  );
  const line = target.locator(".setup-call-line");
  await expect(line).toContainText(
    label("desktop.ledger.apply.outcome.saved_unread"),
  );
  await expect(line).not.toContainText(
    label("desktop.ledger.form.failed", { code: "saved_unread" }),
  );
  await expect(moveUp(target)).toHaveAccessibleName(
    new RegExp(escape(label("desktop.ledger.paused.saved_unread_reason"))),
  );
  await banner(target).locator(".ledger-paused-reread").click();
  await expect(findings(target)).toContainText(
    label("desktop.ledger.paused.found_saved", { movement: label(RULES) }),
  );
});

test("a staged save with an unknown outcome holds an invoice removal elsewhere on the page", async ({
  page: target,
}) => {
  await openLedger(target);
  await typeInto(
    target,
    cellOf(rowOf(target, "PAPELERIA TRAZO"), "counterparty"),
    "Trazo Papelería SL",
  );
  await openReview(target);
  await ledgerControls.nextWrites(target, ["unknown"]);
  await review(target).locator(".ledger-apply-save").click();
  await expect(review(target).locator(".ledger-apply-done")).toBeVisible({
    timeout: 20_000,
  });
  await expect(review(target).locator("[data-outcome=unknown]")).toHaveCount(1);
  await review(target).locator(".ledger-apply-done").click();
  await expect(banner(target)).toContainText(
    label("desktop.ledger.paused.title"),
  );

  // In Invoices, the removal waits for the re-read.
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.invoices") })
    .click();
  await head(target).locator(".ledger-period").click();
  await target.locator(".ledger-period-all").click();
  const invoices = target.locator(".ledger-invoices").getByRole("grid");
  await invoices
    .locator("[data-kind=data]")
    .filter({ hasText: "A-1093" })
    .first()
    .dblclick();
  await expect(editor(target)).toBeVisible();
  await editor(target)
    .getByRole("button", {
      name: label("desktop.ledger.invoices.remove"),
      exact: true,
    })
    .click();
  const remove = editor(target).getByRole("button", {
    name: label("desktop.ledger.invoices.remove_confirm"),
    exact: true,
  });
  await expect(remove).toHaveAttribute("aria-disabled", "true");
  await expect(remove).toHaveAccessibleDescription(
    label("desktop.ledger.tray.paused_reason"),
  );
  // Pressed anyway, it sends nothing.
  await remove.click({ force: true });
  await expect(editor(target)).toBeVisible();
  await expect(remove).toHaveAttribute("aria-disabled", "true");
  await editor(target)
    .getByRole("button", {
      name: label("desktop.ledger.invoices.keep_it"),
      exact: true,
    })
    .click();
  await editor(target)
    .getByRole("button", {
      name: label("desktop.ledger.invoices.close"),
      exact: true,
    })
    .first()
    .click();
  await expect(editor(target)).toBeHidden();
  await expect(
    invoices.locator("[data-kind=data]").filter({ hasText: "A-1093" }),
  ).not.toHaveCount(0);
  // The re-read says the staged save landed, and removal may run again.
  await banner(target).locator(".ledger-paused-reread").click();
  await expect(findings(target)).toContainText(
    label("desktop.ledger.paused.found_saved", {
      movement: "PAPELERIA TRAZO",
    }),
  );
  await invoices
    .locator("[data-kind=data]")
    .filter({ hasText: "A-1093" })
    .first()
    .dblclick();
  await editor(target)
    .getByRole("button", {
      name: label("desktop.ledger.invoices.remove"),
      exact: true,
    })
    .click();
  await expect(remove).not.toHaveAttribute("aria-disabled", "true");
});

test("a link whose invoice could not be read is held until it is read again", async ({
  page: target,
}) => {
  await openLedger(target);
  await stageLink(target, "PAPELERIA TRAZO", "INV-88412");
  await ledgerControls.nextReads(target, "ledger.invoice.list", 1);
  await openReview(target);
  const link = review(target).locator(".ledger-permanent");
  await expect(link.locator(".ledger-link-unread")).toContainText(
    label("desktop.ledger.apply.link.unread"),
  );
  await expect(link.locator(".ledger-link-sure")).toBeDisabled();
  const save = review(target).locator(".ledger-apply-save");
  await expect(save).toHaveAttribute("aria-disabled", "true");
  await link.locator(".ledger-link-reread").click();
  await expect(link.locator(".ledger-link-unread")).toHaveCount(0);
  await expect(link).toContainText("INV-88412");
  await expect(link.locator(".ledger-link-sure")).toBeEnabled();
});

test("a link to an invoice in another currency names it and needs the second tick", async ({
  page: target,
}) => {
  await openLedger(target);
  // The movement is in euros; INV-88412 is in dollars.
  await stageLink(target, "PAPELERIA TRAZO", "INV-88412");
  await openReview(target);
  const link = review(target).locator(".ledger-permanent");
  await expect(link).toContainText(
    label("desktop.ledger.apply.link.currency_differs", {
      movement: "EUR",
      invoice: "USD",
    }),
  );
  const save = review(target).locator(".ledger-apply-save");
  await link.locator(".ledger-link-sure").check();
  await expect(save).toHaveAttribute("aria-disabled", "true");
  await link.locator(".ledger-link-differ").check();
  await expect(save).not.toHaveAttribute("aria-disabled", "true");
});

test("movements a finalized declaration seals are counted as skipped for the selection", async ({
  page: target,
}) => {
  await openLedger(target);
  await head(target).locator(".ledger-period").click();
  const periods = target.getByRole("dialog", {
    name: label("desktop.ledger.period.choose"),
  });
  const shown = periods.locator("[aria-live=polite]");
  for (let guard = 0; guard < 40; guard += 1) {
    const at = Number(await shown.textContent());
    if (at === 2026) break;
    await periods
      .getByRole("button", {
        name: label(
          at > 2026
            ? "desktop.ledger.period.year_previous"
            : "desktop.ledger.period.year_next",
        ),
        exact: true,
      })
      .click();
  }
  await periods
    .getByRole("group", {
      name: label("desktop.ledger.period.of_year", { year: 2026 }),
    })
    .getByRole("button", { name: "1T", exact: true })
    .click();
  await expect(periods).toBeHidden();
  await expect(dataRows(target).first()).toBeVisible();
  // Every movement of 2026 1T is cited by the filed Modelo 303.
  await dataRows(target).nth(0).locator("input[type=checkbox]").click();
  await dataRows(target).nth(1).locator("input[type=checkbox]").click();
  if (!(await panel(target).isVisible()))
    await target.keyboard.press("Alt+KeyI");
  await expect(panel(target)).toContainText(
    label("desktop.ledger.inspector.selection.skipped", { count: 2 }),
  );
});
