import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import type { ModeloDeclarationsListProjectionV1 } from "../../src/shell/modeloContract";
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

/** The list the scenario answers, as the application read it. */
const listed = (shape = "") =>
  JSON.parse(
    readFileSync(
      new URL(
        `../../src/dev/fixtures/modelo/declarations${shape ? `-${shape}` : ""}-en.json`,
        import.meta.url,
      ),
      "utf8",
    ),
  ) as ModeloDeclarationsListProjectionV1;

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
  const read = listed();
  const first = read.rows[0]!;
  const local = read.rows.find(
    (row) => row.modelo === "130" && row.opens_local_work,
  )!;
  await openDeclarations(target);
  await expect(sections(target).first()).toContainText(first.group_words);
  await expect(
    dataRows(target).filter({ hasText: local.modelo_title }).first(),
  ).toContainText(local.state_words);
  // Where the AEAT side stands is said beside the rows, as the list says it.
  for (const notice of read.notices)
    await expect(page(target).locator(".declarations-notice")).toContainText(
      notice,
    );
});

test("an incomplete list never claims there is nothing to do", async ({
  page: target,
}) => {
  // Nothing was ever read from the AEAT in this profile's list.
  const read = listed("incomplete");
  expect(
    read.sources.some((source) => source.availability !== "available"),
  ).toBe(true);
  await openDeclarations(target, "&modelo=incomplete");
  for (const notice of read.notices)
    await expect(page(target).locator(".declarations-notice")).toContainText(
      notice,
    );
  const show = page(target).getByRole("radiogroup", {
    name: label("desktop.declarations.show.label"),
  });
  for (const view of ["todo", "recorded", "all"]) {
    await show
      .getByText(label(`workspace.declarations.list.filter.${view}`))
      .click();
    await expect(
      page(target).getByText(label("workspace.declarations.list.all_recorded")),
    ).toHaveCount(0);
  }
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

test("a column header sorts the list and the sort menu follows it", async ({
  page: target,
}) => {
  await openDeclarations(target);
  const header = (name: string) =>
    grid(target).getByRole("columnheader", { name });
  const modelo = header(label("workspace.declarations.list.column.modelo"));
  const sort = target.locator(".declarations-sort");
  await modelo.click();
  await expect(modelo).toHaveAttribute("aria-sort", "ascending");
  await expect(sort).toHaveValue("modelo");
  await modelo.click();
  await expect(modelo).toHaveAttribute("aria-sort", "descending");
  // The menu stays: choosing the work order drops the column sort.
  await sort.selectOption("work_order");
  await expect(modelo).toHaveAttribute("aria-sort", "none");
  await expect(sections(target).first()).toBeVisible();
});

test("a column is dragged to a width of the person's choosing", async ({
  page: target,
}) => {
  await openDeclarations(target);
  const header = grid(target).getByRole("columnheader", {
    name: label("workspace.declarations.list.column.deadline"),
  });
  const edge = header.getByRole("separator");
  const before = Number(await edge.getAttribute("aria-valuenow"));
  await header.click();
  await header.press("Alt+ArrowRight");
  await expect
    .poll(async () => Number(await edge.getAttribute("aria-valuenow")))
    .toBeGreaterThan(before);
});
