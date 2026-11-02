import { expect, test, type Page } from "@playwright/test";
import { openLedgerAssets } from "../support/ledgerPage";
import { label } from "../support/strings";

// What the Assets tab lays out when a tall form is open above its tables, in
// a window as short as a laptop's: no table sits over another, none is cut to
// a few rows inside its own box, and what does not fit is reached by
// scrolling the area, not lost.

const SHORT = { width: 1440, height: 800 };
const LANGUAGES = ["en", "es"] as const;

/** Each table a person reads in `area`, as the box it is drawn in and the
 * height its rows need. */
const tables = (target: Page, area: string) =>
  target.locator(`${area} [role=group]:has(> table)`).evaluateAll((groups) =>
    groups.map((group) => {
      const box = group.getBoundingClientRect();
      return {
        name: group.getAttribute("aria-label"),
        top: box.top,
        bottom: box.bottom,
        shown: group.clientHeight,
        needed: group.scrollHeight,
      };
    }),
  );

async function expectWholeTables(target: Page, area: string, count: number) {
  const found = await tables(target, area);
  expect(found.length).toBeGreaterThanOrEqual(count);
  for (const table of found) {
    expect(table.shown, `${table.name} is cut to ${table.shown}`).toBe(
      table.needed,
    );
    expect(table.shown).toBeGreaterThan(0);
  }
  const ordered = [...found].sort((a, b) => a.top - b.top);
  for (let at = 1; at < ordered.length; at += 1)
    expect(
      ordered[at]!.top,
      `${ordered[at]!.name} starts over ${ordered[at - 1]!.name}`,
    ).toBeGreaterThanOrEqual(ordered[at - 1]!.bottom);
}

for (const language of LANGUAGES) {
  test(`a stock form opened above the books leaves both tables whole and the area scrolls (${language})`, async ({
    page: target,
  }) => {
    await target.setViewportSize(SHORT);
    await openLedgerAssets(target, { stock: true, language });
    await target
      .getByRole("button", {
        name: label("desktop.ledger.stock.action.add_movement", {}, language),
      })
      .first()
      .click();
    const form = target.locator(".ledger-stock-form-movement");
    await expect(form).toBeVisible();
    // A purchase is the tallest form: its costs and files stand under the price.
    await form
      .getByLabel(label("desktop.ledger.inventory.kind_label", {}, language), {
        exact: true,
      })
      .selectOption("purchase");
    await expectWholeTables(target, ".ledger-stock", 2);
    const reach = await target.locator(".ledger-stock").evaluate((pane) => {
      let scroller = pane.parentElement;
      while (
        scroller &&
        !["auto", "scroll"].includes(getComputedStyle(scroller).overflowY)
      )
        scroller = scroller.parentElement;
      return scroller
        ? { shown: scroller.clientHeight, needed: scroller.scrollHeight }
        : null;
    });
    expect(reach).not.toBeNull();
    expect(reach!.needed).toBeGreaterThan(reach!.shown);
  });

  test(`a register form opened above the elements leaves the list whole (${language})`, async ({
    page: target,
  }) => {
    await target.setViewportSize(SHORT);
    await openLedgerAssets(target, { language });
    await target
      .getByRole("button", {
        name: label("desktop.ledger.assets.action.add", {}, language),
      })
      .click();
    await expect(target.locator(".ledger-asset-form")).toBeVisible();
    await expectWholeTables(target, ".ledger-assets-fixed", 1);
  });

  test(`the amount fields of an element form end in the currency, as percentages end in a sign (${language})`, async ({
    page: target,
  }) => {
    await openLedgerAssets(target, { language });
    await target
      .getByRole("button", {
        name: label("desktop.ledger.assets.action.add", {}, language),
      })
      .click();
    const form = target.locator(".ledger-asset-form");
    for (const key of [
      "basis_amount",
      "non_deductible_iva",
      "residual_value",
    ]) {
      const field = form.locator(`[data-field="${key}"]`);
      await expect(field.locator("[data-slot=money-editor]")).toContainText(
        "€",
      );
    }
  });
}
