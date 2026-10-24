import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The Declarations page over the scenario's modelo family, which answers the
// declarations list the application read for a synthetic taxpayer. The rows,
// their groups, words and notices are the read model's; the page filters,
// sorts and opens them. A new declaration is offered from the read model's
// creation targets, an existing one opens instead of making another, and a
// creation whose settlement was not seen is said to be unknown.

const open = (target: Page, extra = "") =>
  target.goto(`/scenarios.html?scenario=ledger&latency=0&bar=off${extra}`);

const page = (target: Page) => target.locator(".declarations-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const sections = (target: Page) => grid(target).locator("[data-kind=section]");
const dialog = (target: Page) => target.locator(".new-declaration");

async function openDeclarations(target: Page, extra = "") {
  await open(target, extra);
  await target.locator("[data-rail=declarations]").click();
  await expect(dataRows(target).first()).toBeVisible();
}

async function chooseModelo(target: Page, modelo: string, year: number) {
  await page(target).locator(".declarations-new").click();
  await dialog(target)
    .locator(".new-declaration-modelo")
    .filter({ hasText: modelo })
    .first()
    .click();
  await dialog(target)
    .getByRole("radiogroup", {
      name: label("workspace.declarations.list.new.year"),
    })
    .getByText(String(year), { exact: true })
    .click();
}

test("lists the read model's rows in its groups, with its notices", async ({
  page: target,
}) => {
  await openDeclarations(target);
  await expect(sections(target).first()).toContainText("In progress");
  await expect(
    dataRows(target).filter({ hasText: "Modelo 130" }).first(),
  ).toContainText("Calculated, not checked");
  // The AEAT side was never read: the list says so beside its rows.
  await expect(page(target).locator(".declarations-notice")).toContainText(
    "AEAT status",
  );
});

test("an incomplete list never claims there is nothing to do", async ({
  page: target,
}) => {
  await openDeclarations(target);
  await page(target)
    .getByRole("radiogroup", { name: label("desktop.declarations.show.label") })
    .getByText(label("workspace.declarations.list.filter.recorded"))
    .click();
  await expect(page(target).locator(".declarations-empty")).toContainText(
    label("workspace.declarations.list.none_listed"),
  );
});

test("finds a declaration by its modelo", async ({ page: target }) => {
  await openDeclarations(target);
  await page(target).locator(".declarations-search").fill("303");
  const shown = await dataRows(target).allTextContents();
  expect(shown.length).toBeGreaterThan(0);
  for (const row of shown) expect(row).toContain("303");
});

test("a row with local work opens its declaration", async ({
  page: target,
}) => {
  await openDeclarations(target);
  await dataRows(target).filter({ hasText: "Modelo 130" }).first().dblclick();
  await expect(target.locator(".declarations-workspace")).toBeVisible();
  await expect(target.locator(".declarations-workspace")).toBeFocused();
});

test("a period that already has a declaration opens it", async ({
  page: target,
}) => {
  await openDeclarations(target);
  await chooseModelo(target, "130", 2026);
  await dialog(target)
    .getByRole("radio", { name: /1st quarter 2026/ })
    .click();
  const submit = dialog(target).locator(".new-declaration-submit");
  await expect(submit).toHaveText(
    label("workspace.declarations.list.new.open_it"),
  );
  await submit.click();
  await expect(dialog(target)).toBeHidden();
  await expect(target.locator(".declarations-workspace")).toBeVisible();
});

test("a refused creation is said with its code", async ({ page: target }) => {
  await openDeclarations(target, "&modelo=refused");
  await chooseModelo(target, "130", 2026);
  await dialog(target)
    .getByRole("radio", { name: /2nd quarter 2026/ })
    .click();
  await dialog(target).locator(".new-declaration-submit").click();
  await expect(dialog(target).getByRole("alert")).toContainText(
    "operation_denied",
  );
});

test("a creation whose settlement was not seen is unknown and holds", async ({
  page: target,
}) => {
  await openDeclarations(target, "&modelo=unknown");
  await chooseModelo(target, "130", 2026);
  await dialog(target)
    .getByRole("radio", { name: /2nd quarter 2026/ })
    .click();
  const submit = dialog(target).locator(".new-declaration-submit");
  await submit.click();
  await expect(dialog(target).getByRole("alert")).toContainText(
    label("workspace.declarations.list.new.unknown"),
  );
  // Nothing is sent again until the list is read again.
  await expect(submit).toBeDisabled();
});

test("returning from a declaration keeps the list as it was, unread", async ({
  page: target,
}) => {
  await openDeclarations(target);
  const reads = async () =>
    (await target.evaluate(() => window.__scenarioHostCalls ?? [])).filter(
      (call) => call.startsWith("modelo declarations"),
    ).length;
  await page(target).locator(".declarations-search").fill("130");
  const before = await reads();
  await dataRows(target).filter({ hasText: "Modelo 130" }).first().dblclick();
  const workspace = target.locator(".declarations-workspace");
  await expect(workspace).toBeVisible();
  await workspace
    .getByRole("button", {
      name: label("workspace.declarations.destination.overview"),
    })
    .first()
    .click();
  await expect(page(target).locator(".declarations-search")).toHaveValue("130");
  // Nothing was written: the list is the one read before.
  expect(await reads()).toBe(before);
});
