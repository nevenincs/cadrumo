import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { windowFixture } from "../support/windowFixtures";
import { label } from "../support/strings";

// A PDF bank statement only the local AI reads, previewed while the local
// AI cannot read it, is never left without a way to put that right. With
// the local AI set up yet not reading, the row leads to its element of the
// setup panel, where its program and models are shown; with no model picked
// to read with, the row shows the step the backend served, which opens the
// agent's model picker. Every value is synthetic.

const STATEMENT = "movimientos-tarjeta.pdf";
/** The step the backend serves for a role with no picked reading model, as
 * the generated fixture records it. */
const STEP = (
  JSON.parse(
    readFileSync(
      windowFixture("ledger-served-words", "ledgerServedWords"),
      "utf8",
    ),
  ) as { reading_model: { step: Record<string, string> } }
).reading_model.step.en!;

const setupDialog = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.setup.title") });
const picker = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.agent.settings_title") });

/** Opens the Ledger's import on the bank statements and previews every
 * statement it offers; answers the statement's row. */
async function previewStatements(target: Page, query: string) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&${query}`,
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-movements")).toBeVisible();
  await target
    .locator(".pane-docs .pane-head")
    .getByRole("button", {
      name: label("desktop.ledger.action.import"),
      exact: true,
    })
    .click();
  const dialog = target.getByRole("dialog", {
    name: label("desktop.ledger.import.title"),
  });
  await dialog
    .getByRole("button", {
      name: label("desktop.ledger.import.choose_files"),
      exact: true,
    })
    .click();
  await dialog
    .getByRole("button", {
      name: label("desktop.ledger.import.preview"),
      exact: true,
    })
    .click();
  return dialog.getByRole("listitem").filter({ hasText: STATEMENT });
}

test("a PDF statement the local AI does not read although it is set up leads to the local AI's setup", async ({
  page: target,
}) => {
  const card = await previewStatements(
    target,
    "ledger=reader_missing&setup=ready",
  );
  await expect(card).toContainText(
    label("desktop.ledger.import.refusal.reader_unavailable"),
  );
  // A preview opens nothing by itself.
  await expect(setupDialog(target)).toHaveCount(0);
  await card
    .getByRole("button", { name: label("desktop.setup.open"), exact: true })
    .click();
  await expect(setupDialog(target)).toBeVisible();
  await expect(
    setupDialog(target).locator('[data-setup-element="local_ai"]'),
  ).toBeVisible();
});

test("a PDF statement with no reading model picked shows the served step to the model picker", async ({
  page: target,
}) => {
  const card = await previewStatements(target, "ledger=no_reading_model");
  await expect(card).toContainText(
    label("desktop.ledger.import.refusal.reader_unavailable"),
  );
  await expect(card).not.toContainText(
    label("desktop.ledger.import.refusal.reader_unavailable_here"),
  );
  // Nothing is missing from the local AI: no setup is offered.
  await expect(card.locator(".setup-offer")).toHaveCount(0);
  await expect(picker(target)).toHaveCount(0);
  await card.getByRole("button", { name: STEP, exact: true }).click();
  await expect(picker(target)).toBeVisible();
});
