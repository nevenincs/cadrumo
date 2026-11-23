import { expect, test, type Locator, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import { agentColumn as column, openModelPicker } from "../support/agent";
import { label } from "../support/strings";

// The agent's settings in a window as narrow as a phone held upright: the
// models each background task runs with are reached by scrolling the column,
// and the matrix each Change opens, like the composer's, is drawn whole inside
// the window, lays each model out on lines of its own and scrolls inside
// itself rather than moving the page.

const WIDTH = 420;
const HEIGHT = 900;

test.use({
  viewport: { width: WIDTH, height: HEIGHT },
  hasTouch: true,
  isMobile: true,
});

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

/** Opens the agent, which a window this narrow shows on its own. */
async function showAgent(target: Page) {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await target.locator("[data-rail=agent]").tap();
  await expect(column(target)).toBeVisible();
}

const overflowing = (target: Page) =>
  target.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );

/** Waits out the transitions of a popover that is arriving: it grows as it
 * opens, so what is measured of it is only real once they have ended. */
const arrived = (popover: Locator) =>
  popover.evaluate(async (node) => {
    await Promise.all(
      node.getAnimations({ subtree: true }).map((motion) => motion.finished),
    );
  });

/** The words a compact cell shows in place of the column heading over it. */
const columnWords = (column: string) =>
  label(
    column === "default"
      ? "desktop.agent.effort_default"
      : `desktop.agent.effort_${column}`,
  );

/** Checks that `popover` and its matrix fit the window, the matrix laid out
 * for a narrow box and scrolling inside itself; answers its scroller. */
async function fitsTheWindow(target: Page, popover: Locator) {
  await expect(popover).toBeVisible();
  await expect
    .poll(async () => {
      const box = await popover.boundingBox();
      return box ? box.x >= 0 && box.x + box.width <= WIDTH : false;
    })
    .toBe(true);
  await arrived(popover);
  const edge = (await popover.boundingBox())!;
  expect(edge.x).toBeGreaterThanOrEqual(0);
  expect(edge.x + edge.width).toBeLessThanOrEqual(WIDTH);
  expect(edge.y).toBeGreaterThanOrEqual(0);
  expect(edge.y + edge.height).toBeLessThanOrEqual(HEIGHT);
  expect(await overflowing(target)).toBe(false);

  // What scrolls the matrix is held inside the popover, not drawn past it.
  const scroller = popover.locator("[data-slot=model-matrix-scroller]");
  await expect(scroller).toBeVisible();
  const inside = (await scroller.boundingBox())!;
  expect(inside.x).toBeGreaterThanOrEqual(edge.x - 1);
  expect(inside.x + inside.width).toBeLessThanOrEqual(edge.x + edge.width + 1);
  expect(inside.y).toBeGreaterThanOrEqual(edge.y - 1);
  expect(inside.y + inside.height).toBeLessThanOrEqual(
    edge.y + edge.height + 1,
  );
  expect(
    await scroller.evaluate((node) => node.scrollWidth > node.clientWidth),
  ).toBe(false);

  // Nothing drawn of a row reaches past the grid's sides. The column
  // headings are left to a screen reader here, so only the body is measured.
  const grid = scroller.locator("table");
  const cut = await grid.evaluate((table) => {
    const box = table.getBoundingClientRect();
    return [...table.querySelectorAll("tbody [role=radio], tbody th")]
      .filter((node) => {
        const at = node.getBoundingClientRect();
        return at.right > box.right + 1 || at.left < box.left - 1;
      })
      .map((node) => node.textContent ?? "");
  });
  expect(cut).toEqual([]);

  // The compact layout: with no column heading over it, each choice shows
  // its effort in words.
  const cells = await grid
    .locator("tbody [role=radio][data-matrix-cell]")
    .evaluateAll((nodes) =>
      nodes
        .filter((node) => (node as HTMLElement).offsetParent !== null)
        .map((node) => ({
          column: node.getAttribute("data-column") ?? "",
          shown: (node as HTMLElement).innerText.trim(),
        })),
    );
  expect(cells.length).toBeGreaterThan(0);
  expect(cells.map((cell) => cell.shown)).toEqual(
    cells.map((cell) => columnWords(cell.column)),
  );
  expect(cells.map((cell) => cell.column)).toContain("default");

  // A model's name is whole: it wraps rather than being cut.
  const cutNames = await grid
    .locator("tr[data-slot=model-matrix-row] th")
    .evaluateAll((nodes) =>
      nodes
        .filter((node) => node.scrollWidth > node.clientWidth)
        .map((node) => node.textContent ?? ""),
    );
  expect(cutNames).toEqual([]);

  // More rows than fit: the matrix scrolls inside itself, down to its last
  // row, without the window moving.
  expect(
    await scroller.evaluate((node) => node.scrollHeight > node.clientHeight),
  ).toBe(true);
  await scroller.evaluate((node) => {
    node.scrollTop = node.scrollHeight;
  });
  await expect
    .poll(() =>
      scroller.evaluate((node) => {
        const box = node.getBoundingClientRect();
        const row = node
          .querySelector("tbody tr:last-child")
          ?.getBoundingClientRect();
        return row
          ? row.top >= box.top - 1 && row.bottom <= box.bottom + 1
          : false;
      }),
    )
    .toBe(true);
  expect(await overflowing(target)).toBe(false);
  return scroller;
}

test("a task's Change is reached by scrolling, and its matrix fits the window and scrolls inside itself", async ({
  page: target,
}) => {
  await showAgent(target);
  await column(target)
    .getByRole("button", { name: label("desktop.agent.settings"), exact: true })
    .tap();
  const section = column(target)
    .locator("details")
    .filter({ hasText: label("desktop.providers.task_models_title") });
  await section.scrollIntoViewIfNeeded();
  // A section closed before stays closed until its heading is tapped.
  if ((await section.getAttribute("open")) === null)
    await section.locator("summary").tap();

  const [first] = FIXTURE_CATALOG.task_kinds;
  if (!first) throw new Error("The made-up catalogue serves no task kind.");
  // The window says the kinds it knows in its own words.
  const task = label(`desktop.providers.task_kind_${first.id}`);
  const change = section.getByRole("button", {
    name: label("desktop.providers.task_model_change_label", { task }),
  });
  await change.scrollIntoViewIfNeeded();
  await expect(change).toBeInViewport();
  await change.tap();

  const chooser = target.getByRole("dialog", {
    name: label("desktop.providers.task_model_model", { task }),
  });
  const scroller = await fitsTheWindow(target, chooser);

  // A tap on a cell that can be chosen chooses it.
  const cell = scroller
    .locator(
      "tr[data-slot=model-matrix-row]:not([aria-disabled]) [role=radio]:not([aria-disabled])",
    )
    .first();
  await cell.scrollIntoViewIfNeeded();
  await cell.tap();
  await expect(cell).toHaveAttribute("aria-checked", "true");
  expect(await overflowing(target)).toBe(false);
});

test("the composer's model settings fit the window and the matrix scrolls inside itself", async ({
  page: target,
}) => {
  await showAgent(target);
  const settings = await openModelPicker(target);
  await fitsTheWindow(target, settings);
});
