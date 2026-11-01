import { expect, type Page } from "@playwright/test";
import { label } from "./strings";

// The Ledger page as a person works it in the scenario window.

/** Shows a column through the columns menu, as a person does where the
 * page's starting preset gives it up for want of room. */
export async function showLedgerColumn(target: Page, column: string) {
  const ledger = target.locator(".ledger-page");
  await ledger
    .getByRole("button", {
      name: new RegExp(`^${label("desktop.ledger.columns.title")}`),
    })
    .click();
  const box = target
    .locator(`.ledger-columns li[data-column=${column}]`)
    .getByRole("checkbox");
  if (!(await box.isChecked())) await box.check();
  await target.keyboard.press("Escape");
  await expect(
    ledger
      .getByRole("grid")
      .locator(`[role=columnheader][data-header-column=${column}]`),
  ).toHaveCount(1);
}

/** Opens the Ledger's Assets tab in the scenario window, on its Stock area
 * where `stock` is given. */
export async function openLedgerAssets(
  target: Page,
  { stock = false, language = "en" } = {},
) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&lang=${language}`,
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-page").getByRole("grid")).toBeVisible();
  await target
    .locator(".pane-docs .pane-head")
    .getByRole("tab", {
      name: label("desktop.ledger.section.assets", {}, language),
    })
    .click();
  await expect(target.locator(".ledger-assets")).toBeVisible();
  if (stock)
    await target
      .getByRole("tab", {
        name: label("desktop.ledger.assets.area.stock", {}, language),
        exact: true,
      })
      .click();
}
