import { expect, test, type Page } from "@playwright/test";
import {
  purchaseInvoiceFacts,
  purchaseOf,
} from "../../src/components/ledger/assets/assetWrites";
import { exampleInvoices } from "../../src/dev/fixtures/ledgerInvoices";
import type { CatalogueInvoice } from "../../src/shell/ledger";
import type { ActivityAssetRevision } from "../../src/shell/ledgerSetup";
import { label } from "../support/strings";

// Suggestions in the Assets tab over the scenario's ledger: picking a
// supplier in the element's description fills the tax id it left empty and
// leaves one that was typed, and the invoice a purchase was paid by is found
// by the movement it is linked to.

const SUPPLIER = "Coworking Ribera, S.L.";
const SUPPLIER_TAX_ID = "B00000074";

const form = (target: Page) => target.locator(".ledger-asset-form-descriptor");
const input = (target: Page, key: string) =>
  form(target).locator(`[data-field=${key}] input`);

/** Opens the description form of the first element the register lists. */
async function openDescription(target: Page) {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-page").getByRole("grid")).toBeVisible();
  await target
    .locator(".pane-docs .pane-head")
    .getByRole("tab", { name: label("desktop.ledger.section.assets") })
    .click();
  await expect(target.locator(".ledger-assets")).toBeVisible();
  await target
    .locator(".ledger-assets-fixed")
    .getByRole("button", { name: "Furgoneta de reparto", exact: true })
    .click();
  await target
    .getByRole("button", {
      name: label("desktop.ledger.assets.action.describe"),
    })
    .click();
  await expect(form(target)).toBeVisible();
}

/** Types the start of the supplier and chooses it from the list. */
async function pickSupplier(target: Page) {
  const name = input(target, "supplier_name");
  await name.click();
  await name.fill("Coworking");
  await expect(
    target.getByRole("option").filter({ hasText: SUPPLIER }),
  ).toBeVisible();
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Enter");
  await expect(name).toHaveValue(SUPPLIER);
}

test("a supplier picked fills the empty tax id", async ({ page: target }) => {
  await openDescription(target);
  await expect(input(target, "supplier_tax_id")).toHaveValue("");
  await pickSupplier(target);
  await expect(input(target, "supplier_tax_id")).toHaveValue(SUPPLIER_TAX_ID);
});

test("a supplier picked leaves a tax id already typed", async ({
  page: target,
}) => {
  await openDescription(target);
  await input(target, "supplier_tax_id").fill("B12345674");
  await pickSupplier(target);
  await expect(input(target, "supplier_tax_id")).toHaveValue("B12345674");
});

test("a tax id picked fills the empty supplier name", async ({
  page: target,
}) => {
  await openDescription(target);
  const taxId = input(target, "supplier_tax_id");
  await taxId.click();
  await taxId.fill("Ribera");
  await expect(
    target.getByRole("option").filter({ hasText: SUPPLIER }),
  ).toBeVisible();
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Enter");
  await expect(taxId).toHaveValue(SUPPLIER_TAX_ID);
  await expect(input(target, "supplier_name")).toHaveValue(SUPPLIER);
});

test("the suggestions reach no browser storage", async ({ page: target }) => {
  await openDescription(target);
  await pickSupplier(target);
  const stored = await target.evaluate(() =>
    JSON.stringify([{ ...localStorage }, { ...sessionStorage }]).includes(
      "Coworking",
    ),
  );
  expect(stored).toBe(false);
});

test("a new stock book offers the activities held in other years, not one already held", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-page").getByRole("grid")).toBeVisible();
  await target
    .locator(".pane-docs .pane-head")
    .getByRole("tab", { name: label("desktop.ledger.section.assets") })
    .click();
  await target
    .getByRole("tab", {
      name: label("desktop.ledger.assets.area.stock"),
      exact: true,
    })
    .click();
  await target
    .getByRole("button", {
      name: label("desktop.ledger.stock.action.add_book"),
    })
    .click();
  const book = target.locator(".ledger-stock-form-book");
  const name = book.locator("[data-field=name] input");
  await name.fill("Pap");
  await expect(target.getByRole("listbox")).toHaveCount(0);
  await name.fill("Taller");
  await expect(
    target.getByRole("option").filter({ hasText: "Taller de enmarcado" }),
  ).toBeVisible();
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Enter");
  await expect(name).toHaveValue("Taller de enmarcado");
});

// ---- The invoice a purchase was paid by ------------------------------------

const MOVEMENT = "movement-1";
const received = exampleInvoices((text) => text.padEnd(64, "0")).filter(
  (invoice) => invoice.kind === "received",
);
const linked = (invoice: CatalogueInvoice, to: string[]): CatalogueInvoice => ({
  ...invoice,
  linked_transaction_ids: to,
});

test("the one received invoice linked to the purchase states the supplier", () => {
  const [first] = received;
  expect(first).toBeDefined();
  const facts = purchaseInvoiceFacts([linked(first!, [MOVEMENT])], MOVEMENT);
  expect(facts).toEqual({
    supplier_name: first!.counterparty_name,
    supplier_tax_id: first!.counterparty_tax_id,
    document_number: first!.invoice_number,
  });
});

test("an invoice with no tax id states the others only", () => {
  const bare = {
    ...linked(received[0]!, [MOVEMENT]),
    counterparty_tax_id: null,
  };
  const facts = purchaseInvoiceFacts([bare], MOVEMENT);
  expect(facts).not.toHaveProperty("supplier_tax_id");
  expect(facts.supplier_name).toBe(bare.counterparty_name);
});

test("two invoices linked to the purchase, or none, state nothing", () => {
  const [first, second] = received;
  expect(
    purchaseInvoiceFacts(
      [linked(first!, [MOVEMENT]), linked(second!, [MOVEMENT])],
      MOVEMENT,
    ),
  ).toEqual({});
  expect(purchaseInvoiceFacts([linked(first!, ["another"])], MOVEMENT)).toEqual(
    {},
  );
});

test("an invoice the business issued is not the purchase's", () => {
  const issued = exampleInvoices((text) => text.padEnd(64, "0")).find(
    (invoice) => invoice.kind === "issued",
  );
  expect(purchaseInvoiceFacts([linked(issued!, [MOVEMENT])], MOVEMENT)).toEqual(
    {},
  );
});

test("a revision names its purchase by the movement it observed", () => {
  const revision = (acquisition: unknown) =>
    ({
      asset_id: "a",
      revision_number: 1,
      acquisition,
    }) as ActivityAssetRevision;
  expect(purchaseOf(revision({ observed_transaction_id: MOVEMENT }))).toBe(
    MOVEMENT,
  );
  expect(purchaseOf(revision({ observed_transaction_id: null }))).toBeNull();
  expect(purchaseOf(revision(null))).toBeNull();
});
