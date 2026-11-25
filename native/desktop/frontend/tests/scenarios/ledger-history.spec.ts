import { expect, test, type Page } from "@playwright/test";

// The window's back and forward on the Ledger page: Alt+Left and Alt+Right
// step the window's history from anywhere on the page, and only a focused
// grid cell keeps them, as an editing or navigation context keeps its keys.

const ledger = (target: Page) => target.locator(".ledger-page");
const declarations = (target: Page) => target.locator(".declarations-page");

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() =>
    localStorage.removeItem("cadrumo-shell-layout"),
  );
});

/** The Ledger, then the declarations, then the Ledger again. */
async function visit(target: Page) {
  await target.goto(`/scenarios.html?scenario=ledger&latency=0&bar=off`);
  await target.locator("[data-rail=ledger]").click();
  await expect(ledger(target)).toBeVisible();
  await target.locator("[data-rail=declarations]").click();
  await expect(declarations(target)).toBeVisible();
  await target.locator("[data-rail=ledger]").click();
  await expect(ledger(target)).toBeVisible();
}

test("a Ledger grid cell keeps Alt+Left and Alt+Right and the window does not step", async ({
  page: target,
}) => {
  await visit(target);
  const cell = ledger(target)
    .locator('[role="gridcell"][data-column="description"]')
    .first();
  await cell.click();
  await expect(cell).toBeFocused();
  await target.keyboard.press("Alt+ArrowLeft");
  await target.keyboard.press("Alt+ArrowRight");
  await expect(ledger(target)).toBeVisible();
  await expect(declarations(target)).toHaveCount(0);
  await expect(cell).toBeFocused();
});

test("off a grid cell the Ledger page gives Alt+Left and Alt+Right to the window's history", async ({
  page: target,
}) => {
  await visit(target);
  await ledger(target).focus();
  await target.keyboard.press("Alt+ArrowLeft");
  await expect(declarations(target)).toBeVisible();
  await target.keyboard.press("Alt+ArrowRight");
  await expect(ledger(target)).toBeVisible();
  await expect(declarations(target)).toHaveCount(0);

  // A toolbar control on the page is not a grid cell either.
  await target
    .locator(".pane-docs .pane-head")
    .locator(".ledger-period")
    .focus();
  await expect(
    target.locator(".pane-docs .pane-head .ledger-period"),
  ).toBeFocused();
  await target.keyboard.press("Alt+ArrowLeft");
  await expect(declarations(target)).toBeVisible();
});
