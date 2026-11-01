import { expect, test, type Page } from "@playwright/test";
import recorded from "../../src/dev/fixtures/ledgerEntryOptions.json" with { type: "json" };
import { label } from "../support/strings";

// The registry's closed lists in the Invoices section, as the ledger serves
// them: a picker offers what was served, says so when the list could not be
// read, and a stored value stays on offer as itself meanwhile. The served
// answer is the recording of the real operation.

const served = (family: string) =>
  recorded.families
    .find((found) => found.family === family)!
    .options.map((option) => option.value);

const section = (target: Page) => target.locator(".ledger-invoices");
const editor = (target: Page) => target.locator(".ledger-invoice-editor");
const field = (target: Page, key: string) =>
  editor(target)
    .getByLabel(label(`desktop.ledger.invoices.field.${key}`), { exact: true })
    .and(editor(target).locator("input, select, textarea"));

/** The ledger fails its next `count` reads of the entry vocabularies, before
 * the page that reads them is opened. */
const failVocabulary = (target: Page, count: number) =>
  target.evaluate(
    ([definition, times]) =>
      (
        window as unknown as {
          __scenarioLedger: {
            nextReads(definition: string, count: number): void;
          };
        }
      ).__scenarioLedger.nextReads(definition as string, times as number),
    ["ledger.entry-options", count] as const,
  );

async function openInvoices(target: Page, failing = 0) {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  if (failing > 0) await failVocabulary(target, failing);
  await target.locator("[data-rail=ledger]").click();
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.invoices") })
    .click();
  await expect(section(target).getByRole("grid")).toBeVisible();
}

test("the invoice editor offers the classes and IVA categories the ledger served", async ({
  page: target,
}) => {
  await openInvoices(target);
  await target.locator(".pane-docs .pane-head .ledger-add").click();
  await expect(editor(target)).toBeVisible();
  await expect(field(target, "invoice_class").locator("option")).toHaveText(
    served("invoice_class").map((token) =>
      label(`desktop.ledger.invoices.class.${token.toLowerCase()}`),
    ),
  );
  const categories = field(target, "iva_category");
  await expect(categories.locator("option[value]:not([value=''])")).toHaveCount(
    served("iva_category").length,
  );
  await expect(categories.locator("option[disabled]")).toHaveCount(0);
});

test("the class filter says the list is not available when it could not be read", async ({
  page: target,
}) => {
  await openInvoices(target, 1);
  const filter = section(target).locator(".ledger-invoices-class");
  await expect(filter.locator("option[disabled]")).toHaveText(
    label("desktop.ledger.unavailable"),
  );
  // Only the "any class" entry and the notice: no list of its own.
  await expect(filter.locator("option")).toHaveCount(2);
});

test("a stored class stays on offer as itself while the list is not available", async ({
  page: target,
}) => {
  await openInvoices(target, 1);
  await target.locator(".pane-docs .pane-head .ledger-add").click();
  await expect(editor(target)).toBeVisible();
  const classes = field(target, "invoice_class");
  // A new invoice starts as the ordinary class; the unserved list has no word for it.
  await expect(classes).toHaveValue("ORDINARIA");
  await expect(classes.locator("option:checked")).toHaveText("ORDINARIA");
  await expect(classes.locator("option[disabled]")).toHaveText(
    label("desktop.ledger.unavailable"),
  );
});
