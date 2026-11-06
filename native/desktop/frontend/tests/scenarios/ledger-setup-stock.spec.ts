import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import { button, field, openLedger, openAssets } from "../support/ledgerSetup";

test("an inventory valuation preview records nothing", async ({
  page: target,
}) => {
  await openLedger(target);
  await openAssets(target, true);
  const books = target.locator(".ledger-stock-table");
  await expect(books).toBeVisible();
  const listed = books.locator("tr", { hasText: "Papelería y reprografía" });
  const before = await listed.textContent();
  await button(target, "desktop.ledger.stock.action.preview").first().click();
  const valuation = target.locator(".ledger-stock-valuation");
  await expect(valuation).toContainText(
    label("desktop.ledger.inventory.valuation", {
      name: "Papelería y reprografía",
      closing: "410.00",
      cogs: "0.00",
      method: label("application.inventory.labels.valuation_method.fifo"),
    }),
  );
  await expect(valuation).toContainText(
    label("desktop.ledger.inventory.preview_note"),
  );
  // Nothing was recorded: the book lists as it did.
  expect(await listed.textContent()).toBe(before);
});

test("a stock movement's unit cost reads to two places beside its cost", async ({
  page: target,
}) => {
  await openLedger(target);
  await openAssets(target, true);
  await target
    .locator(".ledger-stock-table")
    .getByRole("button", { name: "Papelería y reprografía", exact: true })
    .click();
  const movement = target.locator(".ledger-stock-movements tbody tr").first();
  // The book holds 4.1 and 410: the unit cost shows the cents the cost does.
  await expect(movement.locator("td").nth(3)).toHaveText("4.10");
  await expect(movement.locator("td").nth(4)).toHaveText("410.00");
});

test("a closing value's files and a purchase's files are chosen in the file dialog, and a file the book refuses is said so", async ({
  page: target,
}) => {
  await openLedger(target);
  await openAssets(target, true);
  await button(target, "desktop.ledger.stock.action.closing").first().click();
  const form = target.locator(".ledger-stock-form-closing");
  await expect(form).toBeVisible();
  await field(form, "desktop.ledger.stock.closing.authority").selectOption(
    "physical_observation",
  );
  await expect(
    field(form, "desktop.ledger.stock.closing.counted_on"),
  ).toBeVisible();

  const choose = label("desktop.ledger.stock.proof.choose_file");
  const change = label("desktop.ledger.stock.proof.change_file");
  const counted = label(
    "application.inventory.labels.physical_evidence_role.physical_count",
  );
  const reconciliation = label(
    "application.inventory.labels.decision_evidence_role.authority_reconciliation",
  );

  // A file the book refuses is said so, and the file stays unchosen.
  await target.evaluate(() => window.__scenarioLedger?.nextWrites(["refused"]));
  await form.getByRole("button", { name: `${counted}: ${choose}` }).click();
  await expect(form).toContainText(label("desktop.ledger.stock.refused"));
  await expect(
    form.getByRole("button", { name: `${counted}: ${choose}` }),
  ).toBeVisible();

  // One the book keeps shows its name, and can be changed.
  await form.getByRole("button", { name: `${counted}: ${choose}` }).click();
  await expect(
    form.getByRole("button", { name: `${counted}: ${change}` }),
  ).toBeVisible();
  await expect(form).toContainText("ticket-gasolinera-ruta7.jpg");
  await expect(form).not.toContainText(label("desktop.ledger.stock.refused"));
  await form
    .getByRole("button", { name: `${reconciliation}: ${choose}` })
    .click();
  await expect(
    form.getByRole("button", { name: `${reconciliation}: ${change}` }),
  ).toBeVisible();
  await button(form, "desktop.ledger.form.cancel").click();
  await expect(form).toBeHidden();

  // A purchase's files are offered for a purchase alone.
  await button(target, "desktop.ledger.stock.action.add_movement")
    .first()
    .click();
  const movement = target.locator(".ledger-stock-form-movement");
  const priceFile = movement.getByRole("button", {
    name: `${label("desktop.ledger.stock.proof.price")}: ${choose}`,
  });
  await expect(priceFile).toHaveCount(0);
  await field(movement, "desktop.ledger.inventory.kind_label").selectOption(
    "purchase",
  );
  await expect(priceFile).toBeVisible();
  await field(movement, "desktop.ledger.inventory.kind_label").selectOption(
    "cogs",
  );
  await expect(priceFile).toHaveCount(0);
});
