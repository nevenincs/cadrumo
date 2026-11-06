import { expect, type Locator, type Page } from "@playwright/test";
import { label } from "./strings";

// The Ledger page's Setup sections and Assets tab over the scenario host's
// made-up ledger: how a spec opens the page and reaches a section.

export const head = (target: Page) => target.locator(".pane-docs .pane-head");

export const page = (target: Page) => target.locator(".ledger-page");

export const dataRows = (target: Page) =>
  page(target).getByRole("grid").locator("[data-kind=data]");

export const button = (scope: Page | Locator, key: string, values = {}) =>
  scope.getByRole("button", { name: label(key, values), exact: true });

export const field = (scope: Page | Locator, key: string, values = {}) =>
  scope.getByLabel(label(key, values), { exact: true });

export async function openLedger(
  target: Page,
  scheme?: "light" | "dark",
  language = "en",
  shape?: string,
) {
  if (scheme)
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&lang=${language}${shape ? `&ledger=${shape}` : ""}`,
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(page(target).getByRole("grid")).toBeVisible();
}

export async function openSetup(
  target: Page,
  section: "rules" | "registers" | "health",
  language = "en",
) {
  await head(target).locator(".ledger-setup").click();
  await target
    .getByRole("menuitem", {
      name: label(`desktop.ledger.section.${section}`, {}, language),
    })
    .click();
  await expect(target.locator(`.ledger-setup-${section}`)).toBeVisible();
  // The menu has closed and given the page back.
  await expect(target.getByRole("menu")).toHaveCount(0);
}

/** Opens the Assets tab, on its Stock area where `stock` is given. */
export async function openAssets(target: Page, stock = false, language = "en") {
  await head(target)
    .getByRole("tab", {
      name: label("desktop.ledger.section.assets", {}, language),
    })
    .click();
  await expect(target.locator(".ledger-assets")).toBeVisible();
  if (stock) await area(target, "desktop.ledger.assets.area.stock");
}

export async function area(target: Page, key: string, language = "en") {
  await target
    .getByRole("tab", { name: label(key, {}, language), exact: true })
    .click();
}
