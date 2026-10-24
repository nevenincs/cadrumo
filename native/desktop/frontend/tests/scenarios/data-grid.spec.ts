import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// The data grid and the plain table, mounted alone over made-up rows on the
// primitives page. The page records what the grid asked of its caller in
// `window.__gridEvents`.

const engine = readFileSync(
  fileURLToPath(
    new URL("../../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);

const open = (page: Page, query = "rows=40") =>
  page.goto(`/primitives.html?${query}`);
const grid = (page: Page) => page.getByRole("grid", { name: "Movements" });
const focused = (page: Page) => page.locator(":focus");
const events = (page: Page) =>
  page.evaluate(() => [...(window.__gridEvents ?? [])]);
const live = (page: Page) => page.locator('[aria-live="polite"]');
const primary = process.platform === "darwin" ? "Meta" : "Control";

async function enter(page: Page) {
  await page.keyboard.press("Tab");
  await expect(focused(page)).toHaveAttribute("role", "gridcell");
}

async function audit(page: Page) {
  await page.evaluate(engine);
  return page.evaluate(async () => {
    const axe = (
      window as unknown as {
        axe: {
          run(
            context: unknown,
            options: unknown,
          ): Promise<{ violations: { id: string; nodes: unknown[] }[] }>;
        };
      }
    ).axe;
    const result = await axe.run(document, { resultTypes: ["violations"] });
    return result.violations.map((violation) => violation.id);
  });
}

test("the grid describes all its rows and columns and is one tab stop", async ({
  page,
}) => {
  await open(page);
  const table = grid(page);
  await expect(table).toHaveAttribute("aria-rowcount", "41");
  await expect(table).toHaveAttribute("aria-colcount", "6");
  await expect(table).toHaveAttribute("aria-multiselectable", "true");
  await expect(table.locator('[tabindex="0"]')).toHaveCount(1);
  await expect(
    table.getByRole("columnheader", { name: "Amount" }),
  ).toHaveAttribute("aria-sort", "none");
  await enter(page);
  await expect(focused(page)).toHaveAttribute("aria-colindex", "1");
  await expect(focused(page).locator("xpath=..")).toHaveAttribute(
    "aria-rowindex",
    "2",
  );
  // Tab leaves the grid in navigation.
  await page.keyboard.press("Tab");
  expect(
    await page.evaluate(() =>
      document.querySelector('[role="grid"]')?.contains(document.activeElement),
    ),
  ).toBe(false);
});

test("arrow keys move the active cell and each move is announced", async ({
  page,
}) => {
  await open(page);
  await enter(page);
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await expect(focused(page)).toHaveAttribute("data-column", "description");
  await expect(live(page)).toHaveText(/^Row 1 of 40, Description, /);
  await page.keyboard.press("ArrowDown");
  await expect(focused(page).locator("xpath=..")).toHaveAttribute(
    "aria-rowindex",
    "3",
  );
  await expect(live(page)).toHaveText(/^Row 2 of 40, Description, /);
  await page.keyboard.press("End");
  await expect(focused(page)).toHaveAttribute("data-column", "amount");
  await page.keyboard.press("Home");
  await expect(focused(page)).toHaveAttribute("data-column", "select");
  await page.keyboard.press(`${primary}+End`);
  await expect(focused(page).locator("xpath=..")).toHaveAttribute(
    "aria-rowindex",
    "41",
  );
  await expect(focused(page)).toHaveAttribute("data-column", "amount");
  await page.keyboard.press(`${primary}+Home`);
  await expect(focused(page).locator("xpath=..")).toHaveAttribute(
    "aria-rowindex",
    "2",
  );
  await page.keyboard.press("PageDown");
  const row = Number(
    await focused(page).locator("xpath=..").getAttribute("aria-rowindex"),
  );
  expect(row).toBeGreaterThan(10);
});

test("the header row is reached from the first row and sorts, resizes and reorders", async ({
  page,
}) => {
  await open(page);
  await enter(page);
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowUp");
  await expect(focused(page)).toHaveAttribute("role", "columnheader");
  await expect(focused(page)).toHaveText("Description");
  await page.keyboard.press("Enter");
  await expect(focused(page)).toHaveAttribute("aria-sort", "ascending");
  await page.keyboard.press("Space");
  await expect(focused(page)).toHaveAttribute("aria-sort", "descending");
  const separator = focused(page).getByRole("separator");
  const before = Number(await separator.getAttribute("aria-valuenow"));
  await page.keyboard.press("Alt+ArrowRight");
  await expect
    .poll(async () => Number(await separator.getAttribute("aria-valuenow")))
    .toBeGreaterThan(before);
  await page.keyboard.press(`${primary}+ArrowRight`);
  await expect(focused(page)).toHaveText("Description");
  await expect(focused(page)).toHaveAttribute("aria-colindex", "4");
  await page.keyboard.press("ArrowDown");
  await expect(focused(page)).toHaveAttribute("role", "gridcell");
  await expect(focused(page)).toHaveAttribute("data-column", "description");
  const log = await events(page);
  expect(log).toContain("sort description");
  expect(log.some((line) => line.startsWith("resize description "))).toBe(true);
  expect(log).toContain(
    "order select,date,counterparty,description,category,amount",
  );
});

test("Enter and typing open an editor; Enter, Tab and Escape leave it", async ({
  page,
}) => {
  await open(page);
  await enter(page);
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Enter");
  const editor = page.getByRole("textbox", { name: "Description" });
  await expect(editor).toBeFocused();
  await page.keyboard.type("Stamps");
  await page.keyboard.press("Tab");
  await expect(focused(page)).toHaveAttribute("data-column", "counterparty");
  expect(await events(page)).toContain('commit m1 description "Stamps"');
  // A typed character opens the editor holding it.
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("q");
  await expect(editor).toHaveValue("q");
  await page.keyboard.press("Escape");
  await expect(focused(page)).toHaveAttribute("data-column", "description");
  await expect(focused(page)).toContainText("Stamps");
  // Enter commits and moves down.
  await page.keyboard.press("F2");
  await page.keyboard.press("End");
  await page.keyboard.type(" too");
  await page.keyboard.press("Enter");
  await expect(focused(page).locator("xpath=..")).toHaveAttribute(
    "aria-rowindex",
    "3",
  );
  expect(await events(page)).toContain('commit m1 description "Stamps too"');
  // Delete asks the caller to clear an editable cell.
  await page.keyboard.press("Delete");
  expect(await events(page)).toContain("commit m2 description null");
});

test("a combobox editor is named, grouped and commits with Tab", async ({
  page,
}) => {
  await open(page);
  await enter(page);
  for (let step = 0; step < 4; step += 1)
    await page.keyboard.press("ArrowRight");
  await expect(focused(page)).toHaveAttribute("data-column", "category");
  await page.keyboard.press("e");
  const field = page.getByRole("combobox");
  await expect(field).toBeFocused();
  await expect(field).toHaveValue("e");
  await expect(page.getByRole("listbox")).toHaveAccessibleName(
    /^Category for /,
  );
  await expect(
    page.getByRole("group", { name: "Running costs" }),
  ).toBeVisible();
  await expect(field).toHaveAccessibleDescription(
    "Type to search the categories.",
  );
  await page.keyboard.press("Tab");
  await expect(field).toHaveCount(0);
  await expect(focused(page)).toHaveAttribute("data-column", "amount");
  expect(
    (await events(page)).some((line) => line.startsWith("commit m1 category ")),
  ).toBe(true);
  // Escape leaves the value and returns to the cell.
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("combobox")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("combobox")).toHaveCount(0);
  await expect(focused(page)).toHaveAttribute("data-column", "category");
});

test("cells say what the row's state is, and a read-only cell says why", async ({
  page,
}) => {
  await open(page);
  // The eleventh row is sealed, the thirteenth refused.
  const sealed = grid(page).locator(
    '[aria-rowindex="12"] [data-column="amount"]',
  );
  await expect(sealed).toHaveAttribute("aria-readonly", "true");
  const described = await sealed.evaluate((cell) =>
    (cell.getAttribute("aria-describedby") ?? "")
      .split(" ")
      .map((id) => document.getElementById(id)?.textContent)
      .join(" | "),
  );
  expect(described).toContain("Sealed: Modelo 303 2026 1T");
  expect(described).toContain("Sealed by a filed declaration");
  const refused = grid(page).locator(
    '[aria-rowindex="14"] [data-column="category"]',
  );
  await expect(refused).toHaveAttribute("aria-invalid", "true");
  await expect(refused).toHaveAccessibleDescription(/Refused: this category/);
  await sealed.click();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await expect(live(page)).toHaveText("Sealed by a filed declaration");
  await expect(sealed.locator("xpath=..")).toHaveAttribute(
    "data-state",
    "locked",
  );
});

test("rows are selected by Space, Shift+Space, Ctrl+A and the pointer", async ({
  page,
}) => {
  await open(page);
  await enter(page);
  const row = (index: number) =>
    grid(page).locator(`[aria-rowindex="${index}"]`);
  await page.keyboard.press("Space");
  await expect(row(2)).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  // Shift+Space selects the active row alone, as a spreadsheet does.
  await page.keyboard.press("Shift+Space");
  await expect(row(4)).toHaveAttribute("aria-selected", "true");
  for (const index of [2, 3])
    await expect(row(index)).toHaveAttribute("aria-selected", "false");
  await page.keyboard.press(`${primary}+a`);
  expect(await events(page)).toContain("select all 40");
  await row(6).locator('[data-column="counterparty"]').click();
  await expect(row(6)).toHaveAttribute("aria-selected", "true");
  await expect(row(2)).toHaveAttribute("aria-selected", "false");
  await row(8)
    .locator('[data-column="counterparty"]')
    .click({
      modifiers: [primary],
    });
  await expect(row(6)).toHaveAttribute("aria-selected", "true");
  await expect(row(8)).toHaveAttribute("aria-selected", "true");
  await row(4).getByRole("checkbox").click({ modifiers: [] });
  await expect(row(4)).toHaveAttribute("aria-selected", "true");
  await expect(row(6)).toHaveAttribute("aria-selected", "true");
  const log = await events(page);
  expect(log).toContain("select toggle 1");
  expect(log).toContain("select select 1");
});

test("after Shift+Space, Shift with an arrow extends the row selection", async ({
  page,
}) => {
  await open(page);
  await enter(page);
  const row = (index: number) =>
    grid(page).locator(`[aria-rowindex="${index}"]`);
  await page.keyboard.press("Shift+Space");
  await expect(row(2)).toHaveAttribute("aria-selected", "true");
  for (let step = 0; step < 3; step += 1)
    await page.keyboard.press("Shift+ArrowDown");
  for (const index of [2, 3, 4, 5])
    await expect(row(index)).toHaveAttribute("aria-selected", "true");
  await expect(row(6)).toHaveAttribute("aria-selected", "false");
  await page.keyboard.press("Shift+ArrowUp");
  await expect(row(5)).toHaveAttribute("aria-selected", "false");
  await expect(row(4)).toHaveAttribute("aria-selected", "true");
  // A plain move leaves row mode: Shift with an arrow is a cell range again.
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Shift+ArrowDown");
  await expect(row(6)).toHaveAttribute("aria-selected", "false");
  for (const index of [2, 3, 4])
    await expect(row(index)).toHaveAttribute("aria-selected", "true");
});

test("after moving away from the anchor, Shift+Space and Shift+arrows select what the range draws", async ({
  page,
}) => {
  await open(page);
  await enter(page);
  const row = (index: number) =>
    grid(page).locator(`[aria-rowindex="${index}"]`);
  await page.keyboard.press("Space");
  for (let step = 0; step < 5; step += 1)
    await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Shift+Space");
  await page.keyboard.press("Shift+ArrowDown");
  await page.keyboard.press("Shift+ArrowDown");
  // The rows the range covers are the rows selected, and no others.
  const ranged = await grid(page)
    .locator("[role=row]:has([data-in-range])")
    .evaluateAll((rows) =>
      rows.map((row) => row.getAttribute("aria-rowindex")),
    );
  const selected = await grid(page)
    .locator("[role=row][aria-selected=true]")
    .evaluateAll((rows) =>
      rows.map((row) => row.getAttribute("aria-rowindex")),
    );
  expect(ranged).toEqual(["7", "8", "9"]);
  expect(selected).toEqual(ranged);
  await expect(row(2)).toHaveAttribute("aria-selected", "false");
});

test("a range is drawn, copied, filled and offered to the menu", async ({
  page,
}) => {
  await open(page);
  await enter(page);
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Shift+ArrowRight");
  await page.keyboard.press("Shift+ArrowDown");
  await expect(grid(page).locator("[data-in-range]")).toHaveCount(4);
  const copied = await focused(page).evaluate((cell) => {
    const data = new DataTransfer();
    const event = new ClipboardEvent("copy", {
      clipboardData: data,
      bubbles: true,
      cancelable: true,
    });
    cell.dispatchEvent(event);
    return { text: data.getData("text/plain"), taken: event.defaultPrevented };
  });
  expect(copied.taken).toBe(true);
  expect(copied.text.split("\n")).toHaveLength(2);
  expect(copied.text.split("\n")[0]?.split("\t")).toHaveLength(2);
  await focused(page).evaluate((cell) => {
    const data = new DataTransfer();
    data.setData("text/plain", "a\tb");
    cell.dispatchEvent(
      new ClipboardEvent("paste", {
        clipboardData: data,
        bubbles: true,
        cancelable: true,
      }),
    );
  });
  await page.keyboard.press(`${primary}+d`);
  await page.keyboard.press("Shift+F10");
  await page.keyboard.press("Escape");
  await expect(grid(page).locator("[data-in-range]")).toHaveCount(0);
  const log = await events(page);
  expect(log).toContain("copy 2x2");
  expect(log).toContain("paste 2x2 a\tb");
  expect(log).toContain("fill down 2x2");
  expect(log).toContain("menu m2 counterparty");
});

test("ten thousand rows keep a bounded document and reach the last row", async ({
  page,
}) => {
  await open(page, "rows=10000");
  const table = grid(page);
  await expect(table).toHaveAttribute("aria-rowcount", "10001");
  const drawn = () => table.locator('[role="row"]').count();
  expect(await drawn()).toBeLessThan(80);
  await enter(page);
  await page.keyboard.press(`${primary}+End`);
  await expect(focused(page).locator("xpath=..")).toHaveAttribute(
    "aria-rowindex",
    "10001",
  );
  await expect(live(page)).toHaveText(/^Row 10000 of 10000, Amount, /);
  expect(await drawn()).toBeLessThan(80);
  await page.keyboard.press("PageUp");
  expect(await drawn()).toBeLessThan(80);
});

test("sections are one cell across the grid that folds with the arrows", async ({
  page,
}) => {
  await open(page, "rows=60&grouped");
  await enter(page);
  const section = focused(page);
  await expect(section).toHaveAttribute("aria-colspan", "6");
  await expect(section).toHaveAttribute("aria-expanded", "true");
  await expect(section).toContainText("January 2026");
  await expect(section).toContainText("Movements of the month");
  await page.keyboard.press("ArrowLeft");
  await expect(focused(page)).toHaveAttribute("aria-expanded", "false");
  await page.keyboard.press("ArrowRight");
  await expect(focused(page)).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("ArrowDown");
  await expect(focused(page)).toHaveAttribute("role", "gridcell");
  await expect(focused(page)).toHaveAttribute("data-column", "select");
  expect(await events(page)).toEqual([
    "toggle month-2026-01",
    "toggle month-2026-01",
  ]);
});

test("the plain table shows section hints and keeps the open row through a new sort", async ({
  page,
}) => {
  await open(page, "harness=table");
  const table = page.getByRole("table", { name: "Declarations" });
  const soon = table.getByRole("rowheader", { name: /Due soon/ });
  await expect(soon).toContainText("Due within a week, or stopped");
  const current = table.locator('[aria-current="true"]');
  await expect(current).toHaveCount(1);
  await expect(current).toContainText("130");
  const order = () =>
    table
      .locator('[data-slot="data-table-row"] td:first-child')
      .allTextContents();
  const before = await order();
  await table.getByRole("button", { name: "Modelo" }).click();
  await expect(
    table.getByRole("columnheader", { name: "Modelo" }),
  ).toHaveAttribute("aria-sort", "descending");
  expect(await order()).not.toEqual(before);
  await expect(current).toHaveCount(1);
  await expect(current).toContainText("130");
  await table.getByRole("button", { name: "Due" }).click();
  await expect(current).toContainText("130");
  // One tab stop: the open row; the arrows move and Enter opens.
  await current.focus();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(current).toHaveCount(1);
  await expect(current).toBeFocused();
  expect((await events(page)).length).toBe(1);
});

for (const scheme of ["light", "dark"] as const) {
  test(`the grid and the table pass an accessibility audit in the ${scheme} scheme`, async ({
    page,
  }) => {
    await open(page, `rows=40&grouped&scheme=${scheme}`);
    await enter(page);
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Space");
    expect(await audit(page)).toEqual([]);
    await open(page, `harness=table&scheme=${scheme}`);
    expect(await audit(page)).toEqual([]);
  });
}

test("a sheet is modal, closes on Escape and returns focus to its opener", async ({
  page,
}) => {
  await open(page, "harness=companions");
  const opener = page.getByRole("button", { name: "Edit invoice" });
  await opener.click();
  const sheet = page.getByRole("dialog", { name: "Edit invoice" });
  await expect(sheet).toBeVisible();
  await expect(sheet).toHaveAccessibleDescription(
    "Changes stay here until you save them.",
  );
  // Focus stays inside while it is open.
  for (let step = 0; step < 4; step += 1) {
    await page.keyboard.press("Tab");
    expect(
      await sheet.evaluate((element) =>
        element.contains(document.activeElement),
      ),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(sheet).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("a filter chip removes itself with a named, finger-sized button", async ({
  page,
}) => {
  await open(page, "harness=companions");
  const remove = page.getByRole("button", {
    name: "Remove filter: Category is Rent",
  });
  const box = await remove.boundingBox();
  expect(box?.width).toBeGreaterThanOrEqual(24);
  expect(box?.height).toBeGreaterThanOrEqual(24);
  await remove.click();
  await expect(page.getByText("Category is Rent")).toHaveCount(0);
  await expect(page.getByText("Amount over 100.00")).toBeVisible();
  expect(await audit(page)).toEqual([]);
});
