import { expect, test, type Locator, type Page } from "@playwright/test";
import { label } from "../support/strings";

// Suggestions in the document reading, the evidence records and a stored
// invoice, over the `documents` ledger: a pick fills the sibling the person
// left empty and keeps one that was typed or read, a stored invoice's pick
// fills nothing else, and nothing offered is kept in browser storage.

const DOMESTIKA = "factura-domestika-lettering.pdf";
const PLENOIL = "ticket-plenoil-1015.jpg";
const ARROYO = "factura-arroyo-2026-10.pdf";

const section = (target: Page) => target.locator(".ledger-documents");
const draft = (target: Page) => section(target).locator(".ledger-draft");
const options = (target: Page) =>
  target.getByRole("listbox").getByRole("option");

async function openDocuments(target: Page) {
  await target.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&ledger=documents",
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-movements")).toBeVisible();
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.documents") })
    .click();
  await expect(section(target)).toBeVisible();
}

async function reading(target: Page, name: string) {
  await openDocuments(target);
  await section(target)
    .locator(".ledger-review-item")
    .filter({ hasText: name })
    .click();
  await expect(draft(target).getByRole("heading", { name })).toBeVisible();
  await draft(target)
    .locator(".ledger-draft-kind")
    .getByRole("radio", {
      name: label("desktop.ledger.invoices.kind_choice.received"),
    })
    .click();
}

const cell = (target: Page, field: string): Locator =>
  draft(target).locator(`[data-field=${field}] input`);

/** Types the start of the catalogue's supplier and picks it by the pointer. */
async function pickSupplier(target: Page) {
  await cell(target, "counterparty_name").fill("Arroyo");
  const arroyo = options(target).filter({ hasText: "Arroyo Asesores SL" });
  await expect(arroyo).toHaveCount(1);
  await arroyo.click();
  await expect(cell(target, "counterparty_name")).toHaveValue(
    "Arroyo Asesores SL",
  );
}

test("a party picked in a reading fills the tax id the reading left empty", async ({
  page: target,
}) => {
  await reading(target, PLENOIL);
  await expect(cell(target, "counterparty_tax_id")).toHaveValue("");
  await pickSupplier(target);
  await expect(cell(target, "counterparty_tax_id")).toHaveValue("B98000013");
  await expect(cell(target, "counterparty_name")).toBeFocused();
});

test("a party picked in a reading leaves a tax id that was typed", async ({
  page: target,
}) => {
  await reading(target, PLENOIL);
  await cell(target, "counterparty_tax_id").fill("B87000001");
  await pickSupplier(target);
  await expect(cell(target, "counterparty_tax_id")).toHaveValue("B87000001");
});

test("a party picked in a reading leaves a tax id that was read", async ({
  page: target,
}) => {
  await reading(target, DOMESTIKA);
  await expect(cell(target, "counterparty_tax_id")).toHaveValue("B66000099");
  await pickSupplier(target);
  await expect(cell(target, "counterparty_tax_id")).toHaveValue("B66000099");
});

test("a tax id picked in a reading fills the name only while it is untouched", async ({
  page: target,
}) => {
  await reading(target, PLENOIL);
  // A name the person cleared is theirs: the pick leaves it empty.
  await cell(target, "counterparty_name").fill("");
  await cell(target, "counterparty_tax_id").fill("B9800");
  const arroyo = options(target).filter({ hasText: "B98000013" });
  await expect(arroyo).toHaveCount(1);
  await arroyo.click();
  await expect(cell(target, "counterparty_tax_id")).toHaveValue("B98000013");
  await expect(cell(target, "counterparty_name")).toHaveValue("");
  await expect(cell(target, "invoice_number")).toHaveValue("T-1015-0042");
  // The country is the person's own answer, not part of a pick here.
  await expect(draft(target).locator(".ledger-draft-country")).toHaveValue("");
});

test("invoice numbers offer the chosen party's own and keep the rest as typed", async ({
  page: target,
}) => {
  await reading(target, PLENOIL);
  await pickSupplier(target);
  await cell(target, "invoice_number").fill("AA-2026-1");
  await expect(options(target)).toHaveCount(3);
  await options(target).filter({ hasText: "AA-2026-119" }).click();
  await expect(cell(target, "invoice_number")).toHaveValue("AA-2026-119");
  await expect(cell(target, "counterparty_name")).toHaveValue(
    "Arroyo Asesores SL",
  );
  await expect(cell(target, "series")).toHaveValue("");
});

test("Enter keeps what was typed until an option is highlighted", async ({
  page: target,
}) => {
  await reading(target, PLENOIL);
  await cell(target, "counterparty_name").fill("Arroyo");
  await expect(options(target)).toHaveCount(1);
  await target.keyboard.press("Enter");
  await expect(cell(target, "counterparty_name")).toHaveValue("Arroyo");
  await expect(cell(target, "counterparty_tax_id")).toHaveValue("");
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Enter");
  await expect(cell(target, "counterparty_name")).toHaveValue(
    "Arroyo Asesores SL",
  );
});

test("the country of a reading offers the codes in use", async ({
  page: target,
}) => {
  await reading(target, DOMESTIKA);
  const country = draft(target).locator(".ledger-draft-country");
  await country.focus();
  await target.keyboard.press("ArrowDown");
  const spain = options(target).filter({ hasText: /^ES/ });
  await expect(spain).toHaveCount(1);
  await target.keyboard.press("Enter");
  await expect(country).toHaveValue(/^ES/);
});

test("the currency of a reading offers the codes in use", async ({
  page: target,
}) => {
  await reading(target, PLENOIL);
  const currency = cell(target, "currency");
  await currency.fill("E");
  await expect(options(target).filter({ hasText: /^EUR/ })).toHaveCount(1);
  await options(target).first().click();
  await expect(currency).toHaveValue("EUR");
});

test("an evidence record offers the catalogue's suppliers and this supplier's numbers", async ({
  page: target,
}) => {
  await openDocuments(target);
  await section(target)
    .getByRole("tab", {
      name: new RegExp(`^${label("desktop.ledger.documents.tab.records")}`),
    })
    .click();
  await section(target)
    .locator(".ledger-record-item")
    .filter({ hasText: ARROYO })
    .click();
  const detail = section(target).locator(".ledger-record");
  const supplier = detail.getByLabel(
    label("desktop.ledger.documents.record.supplier"),
  );
  const number = detail.getByLabel(
    label("desktop.ledger.documents.record.invoice_number"),
  );
  const held = await number.inputValue();
  await supplier.fill("Impr");
  await expect(options(target)).toHaveCount(1);
  await options(target).first().click();
  await expect(supplier).toHaveValue("Imprenta Gráficas Turia SL");
  // A supplier pick fills no other field.
  await expect(number).toHaveValue(held);
  await number.fill("GT-");
  await expect(options(target)).toHaveCount(1);
  await expect(options(target).first()).toContainText("GT-2026-0917");
});

test("a stored invoice's pick fills nothing else, and its payment id offers its linked movements", async ({
  page: target,
}) => {
  await openDocuments(target);
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.invoices") })
    .click();
  const invoices = target.locator(".ledger-invoices");
  await expect(invoices.getByRole("grid")).toBeVisible();
  await target.locator(".pane-docs .pane-head .ledger-period").click();
  await target.locator(".ledger-period-all").click();
  await invoices
    .getByRole("grid")
    .locator("[data-kind=data]")
    .filter({ hasText: "AA-2026-104" })
    .first()
    .dblclick();
  const editor = target.locator(".ledger-invoice-editor");
  await expect(editor).toBeVisible();
  const field = (key: string) =>
    editor
      .getByLabel(label(`desktop.ledger.invoices.field.${key}`), {
        exact: true,
      })
      .and(editor.locator("input, select, textarea"));

  const country = await field("counterparty_country").inputValue();
  await field("counterparty_name").fill("Impr");
  await expect(options(target)).toHaveCount(1);
  await options(target).first().click();
  await expect(field("counterparty_name")).toHaveValue(
    "Imprenta Gráficas Turia SL",
  );
  await expect(field("counterparty_country")).toHaveValue(country);

  await field("payment_id").focus();
  await target.keyboard.press("ArrowDown");
  await expect(options(target)).toHaveCount(1);
  await expect(options(target).first()).toHaveText(/^[0-9a-f]{64}$/);
  await target.keyboard.press("Enter");
  await expect(field("payment_id")).toHaveValue(/^[0-9a-f]{64}$/);

  await field("series").focus();
  await expect(field("series")).toHaveAttribute("role", "combobox");
  await expect(field("rectifies_invoice_number")).toHaveCount(0);

  const stored = await target.evaluate(() =>
    [localStorage, sessionStorage]
      .flatMap((area) =>
        Array.from({ length: area.length }, (_, at) => {
          const key = area.key(at)!;
          return `${key}=${area.getItem(key)}`;
        }),
      )
      .join("\n"),
  );
  expect(stored).not.toContain("Imprenta");
  expect(stored).not.toMatch(/[0-9a-f]{64}/);
});
