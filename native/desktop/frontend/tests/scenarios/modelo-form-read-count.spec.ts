import { expect, type Page, test } from "@playwright/test";
import { label } from "../support/strings";
import {
  boxRow,
  list,
  openDeclaration,
  openList,
  rowsOf,
} from "../support/scenarioModelo";

// The whole Modelo form read takes seconds, so the window asks for it once
// per moment that needs it: once when a declaration opens and once when the
// person comes back to it from another page. A second ask at either moment
// holds the declaration read-only for another full read.

declare global {
  interface Window {
    __formReads?: number;
  }
}

const countReads = (target: Page) =>
  target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const read = port.form;
    window.__formReads = 0;
    port.form = (...args) => {
      window.__formReads = (window.__formReads ?? 0) + 1;
      return read(...args);
    };
  });
const reads = (target: Page) => target.evaluate(() => window.__formReads ?? 0);

async function settle(target: Page) {
  await expect(boxRow(target, "06")).toBeVisible();
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  // A repeat starts after the first read lands, so give it the time it needs.
  await target.waitForTimeout(1500);
}

test("opening a declaration reads its form once", async ({ page: target }) => {
  const grid = await openList(target, { shape: "edit" });
  await countReads(target);
  const local = list().rows.find(
    (row) => row.modelo === "130" && row.opens_local_work,
  );
  if (!local) throw new Error("no local declaration of 130 is listed");
  await target
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label"),
    })
    .fill("130");
  await rowsOf(grid, "130")
    .filter({ hasText: local.period_words ?? local.modelo_title })
    .filter({ hasText: local.state_words })
    .first()
    .dblclick();
  await settle(target);
  expect(await reads(target)).toBe(1);
});

test("returning to a declaration from another page reads its form once", async ({
  page: target,
}) => {
  await openDeclaration(target, "130", { shape: "edit" });
  await settle(target);
  await countReads(target);
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator("section.ledger-page")).toBeVisible();
  await target.locator("[data-rail=declarations]").click();
  await settle(target);
  expect(await reads(target)).toBe(1);
});

test("returning twice reads the form once each time", async ({
  page: target,
}) => {
  await openDeclaration(target, "130", { shape: "edit" });
  await settle(target);
  await countReads(target);
  for (let round = 1; round <= 2; round += 1) {
    await target.locator("[data-rail=ledger]").click();
    await expect(target.locator("section.ledger-page")).toBeVisible();
    await target.locator("[data-rail=declarations]").click();
    await settle(target);
    expect(await reads(target)).toBe(round);
  }
});
