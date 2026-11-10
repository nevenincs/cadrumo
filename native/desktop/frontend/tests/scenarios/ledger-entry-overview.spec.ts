import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { label } from "../support/strings";

// The overview of one ledger entry over the scenario's ledger: a movement,
// an invoice and an evidence record, each opened with Alt+Enter where the
// focus is and from its row's context menu. It shows what the row stores,
// only reads, keeps the focus inside while open, and gives it back to where
// it was asked from as Escape closes it.

const engine = readFileSync(
  fileURLToPath(
    new URL("../../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);

const MOVEMENT = "PAPELERIA TRAZO";

async function open(target: Page, extra = "", scheme?: "light" | "dark") {
  if (scheme)
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off${extra}`,
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-movements")).toBeVisible();
}

const overview = (target: Page) =>
  target.getByRole("dialog").and(target.locator(".ledger-overview"));
const fact = (target: Page, id: string) =>
  overview(target).locator(`[data-fact="${id}"] dd`);
const menuItem = (target: Page, key: string) =>
  target
    .getByRole("menuitem")
    .filter({ hasText: label(key) })
    .first();

// ---- Movements ---------------------------------------------------------------

const movementGrid = (target: Page) =>
  target.locator(".ledger-page .ledger-movements").getByRole("grid");
const movementRow = (target: Page) =>
  movementGrid(target)
    .locator("[data-kind=data]")
    .filter({
      has: target.locator("[data-column=description]", { hasText: MOVEMENT }),
    })
    .first();
const cellOf = (row: Locator, column: string) =>
  row.locator(`[data-column=${column}]`);

/** The movement's own cells say what the overview must say. */
async function expectMovementFacts(target: Page) {
  const row = movementRow(target);
  const description = (await cellOf(row, "description").innerText()).trim();
  await expect(overview(target).locator(".ledger-overview-title")).toHaveText(
    description,
  );
  const counterparty = (await cellOf(row, "counterparty").innerText()).trim();
  if (counterparty)
    await expect(
      overview(target).locator(".ledger-overview-subtitle"),
    ).toContainText(counterparty);
  const classification = (
    await cellOf(row, "classification").innerText()
  ).trim();
  await expect(fact(target, "business_classification")).toHaveText(
    classification,
  );
  // A read view: nothing in it takes typing.
  await expect(overview(target).locator("input, select, textarea")).toHaveCount(
    0,
  );
}

async function focusOnMovement(target: Page) {
  await expect
    .poll(() =>
      target.evaluate(
        (text) =>
          document.activeElement
            ?.closest("[data-kind=data]")
            ?.querySelector("[data-column=description]")
            ?.textContent?.includes(text) ?? false,
        MOVEMENT,
      ),
    )
    .toBe(true);
}

test("a movement's overview opens with Alt+Enter and shows the row's facts; Escape returns focus to the cell", async ({
  page: target,
}) => {
  await open(target);
  await cellOf(movementRow(target), "description").click();
  await target.keyboard.press("Alt+Enter");
  await expect(overview(target)).toBeVisible();
  // Plain Enter still opens the cell editor, never the overview.
  await expect(target.locator(".ledger-cell-editor")).toHaveCount(0);
  await expectMovementFacts(target);
  await target.keyboard.press("Escape");
  await expect(overview(target)).toHaveCount(0);
  await focusOnMovement(target);
});

test("a movement's overview opens from the row's context menu", async ({
  page: target,
}) => {
  await open(target);
  await cellOf(movementRow(target), "counterparty").click({ button: "right" });
  await menuItem(target, "desktop.ledger.overview.show").click();
  await expect(overview(target)).toBeVisible();
  await expectMovementFacts(target);
  await target.keyboard.press("Escape");
  await expect(overview(target)).toHaveCount(0);
  await focusOnMovement(target);
});

// ---- Invoices ----------------------------------------------------------------

async function openInvoices(target: Page) {
  await open(target);
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.invoices") })
    .click();
  await expect(
    target.locator(".ledger-invoices").getByRole("grid"),
  ).toBeVisible();
}
const invoiceRow = (target: Page) =>
  target
    .locator(".ledger-invoices")
    .getByRole("grid")
    .locator("[data-kind=data]")
    .first();

async function expectInvoiceFacts(target: Page) {
  const row = invoiceRow(target);
  const number = (
    await row.locator(".ledger-invoice-number").innerText()
  ).trim();
  const counterparty = (await cellOf(row, "counterparty").innerText()).trim();
  const total = (await cellOf(row, "total").innerText()).trim();
  await expect(overview(target).locator(".ledger-overview-title")).toHaveText(
    counterparty,
  );
  await expect(
    overview(target).locator(".ledger-overview-subtitle"),
  ).toContainText(number);
  await expect(fact(target, "grand_total")).toHaveText(total);
}

test("an invoice's overview opens with Alt+Enter and from the context menu, and matches the grid row", async ({
  page: target,
}) => {
  await openInvoices(target);
  await cellOf(invoiceRow(target), "counterparty").click();
  await target.keyboard.press("Alt+Enter");
  await expect(overview(target)).toBeVisible();
  await expect(target.locator(".ledger-invoice-editor")).toHaveCount(0);
  await expectInvoiceFacts(target);
  await target.keyboard.press("Escape");
  await expect(overview(target)).toHaveCount(0);
  await expect
    .poll(() =>
      target.evaluate(
        () =>
          document.activeElement?.closest(".ledger-invoices [role=grid]") !==
          null,
      ),
    )
    .toBe(true);

  await cellOf(invoiceRow(target), "counterparty").click({ button: "right" });
  await menuItem(target, "desktop.ledger.overview.show").click();
  await expect(overview(target)).toBeVisible();
  await expectInvoiceFacts(target);
});

// ---- Documents ---------------------------------------------------------------

async function openRecords(target: Page) {
  await open(target, "&ledger=documents");
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.documents") })
    .click();
  await target
    .locator(".ledger-documents")
    .getByRole("tab", {
      name: new RegExp(`^${label("desktop.ledger.documents.tab.records")}`),
    })
    .click();
  await expect(target.locator(".ledger-record-item").first()).toBeVisible();
}

test("a document record's overview opens with Alt+Enter and from the context menu", async ({
  page: target,
}) => {
  await openRecords(target);
  const item = target.locator(".ledger-record-item").first();
  const name = (
    await item.locator("span.truncate.font-medium").innerText()
  ).trim();
  await item.focus();
  await target.keyboard.press("Alt+Enter");
  await expect(overview(target)).toBeVisible();
  await expect(overview(target).locator(".ledger-overview-title")).toHaveText(
    name,
  );
  await target.keyboard.press("Escape");
  await expect(overview(target)).toHaveCount(0);
  await expect(item).toBeFocused();

  await item.click({ button: "right" });
  await menuItem(target, "desktop.ledger.overview.show").click();
  await expect(overview(target)).toBeVisible();
  await expect(overview(target).locator(".ledger-overview-title")).toHaveText(
    name,
  );
  await target.keyboard.press("Escape");
  await expect(item).toBeFocused();
});

// ---- The action and the window -----------------------------------------------

test("the overview's action opens the inspector, the invoice editor and the record", async ({
  page: target,
}) => {
  await open(target);
  await cellOf(movementRow(target), "description").click();
  await target.keyboard.press("Alt+Enter");
  await overview(target)
    .getByRole("button", {
      name: label("desktop.ledger.overview.open_movement"),
    })
    .click();
  await expect(overview(target)).toHaveCount(0);
  await expect(target.locator(".ledger-inspector")).toBeVisible();

  await target
    .getByRole("tab", { name: label("desktop.ledger.section.invoices") })
    .click();
  await cellOf(invoiceRow(target), "counterparty").click();
  await target.keyboard.press("Alt+Enter");
  await overview(target)
    .getByRole("button", {
      name: label("desktop.ledger.inspector.invoice.open"),
    })
    .click();
  await expect(target.locator(".ledger-invoice-editor")).toBeVisible();
});

test("the overview's action opens the evidence record", async ({
  page: target,
}) => {
  await openRecords(target);
  const item = target.locator(".ledger-record-item").first();
  await item.focus();
  await target.keyboard.press("Alt+Enter");
  await overview(target)
    .getByRole("button", { name: label("desktop.ledger.overview.open_record") })
    .click();
  await expect(overview(target)).toHaveCount(0);
  await expect(item).toHaveAttribute("aria-current", "true");
  await expect(target.locator(".ledger-record-none")).toHaveCount(0);
});

test("the overview keeps the focus inside while open", async ({
  page: target,
}) => {
  await open(target);
  await cellOf(movementRow(target), "description").click();
  await target.keyboard.press("Alt+Enter");
  await expect(overview(target)).toBeVisible();
  for (const key of ["Tab", "Tab", "Tab", "Tab", "Shift+Tab", "Shift+Tab"]) {
    await target.keyboard.press(key);
    expect(
      await target.evaluate(
        () => document.activeElement?.closest(".ledger-overview") !== null,
      ),
    ).toBe(true);
  }
});

test("the overview fits a narrow window without horizontal scroll", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 480, height: 800 });
  await open(target);
  await cellOf(movementRow(target), "description").click();
  await target.keyboard.press("Alt+Enter");
  await expect(overview(target)).toBeVisible();
  const { scroll, client } = await overview(target).evaluate((element) => ({
    scroll: element.scrollWidth,
    client: element.clientWidth,
  }));
  expect(scroll).toBeLessThanOrEqual(client);
});

async function audit(target: Page) {
  await target.evaluate(engine);
  return target.evaluate(async () => {
    const axe = (
      window as unknown as {
        axe: {
          run(
            context: unknown,
            options: unknown,
          ): Promise<{
            violations: { id: string; nodes: { target: string[] }[] }[];
          }>;
        };
      }
    ).axe;
    const result = await axe.run(
      { exclude: [[".docs-frame"], [".xterm"]] },
      { resultTypes: ["violations"] },
    );
    return result.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.map((node) => node.target.join(" ")),
    }));
  });
}

for (const scheme of ["light", "dark"] as const)
  test(`the overview has no accessibility violations (${scheme})`, async ({
    page: target,
  }) => {
    await open(target, "", scheme);
    await expect(target.locator("html")).toHaveAttribute("data-scheme", scheme);
    await cellOf(movementRow(target), "description").click();
    await target.keyboard.press("Alt+Enter");
    await expect(overview(target)).toBeVisible();
    expect(await audit(target)).toEqual([]);
    await target.keyboard.press("Escape");
    await target
      .getByRole("tab", { name: label("desktop.ledger.section.invoices") })
      .click();
    await cellOf(invoiceRow(target), "counterparty").click();
    await target.keyboard.press("Alt+Enter");
    await expect(overview(target)).toBeVisible();
    expect(await audit(target)).toEqual([]);
  });
