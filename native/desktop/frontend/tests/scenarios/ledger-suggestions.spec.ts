import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// Suggestions in the invoice editor over the scenario's ledger: a pick fills
// what is empty and leaves what was typed; Enter and Tab keep typed text unless
// an option is highlighted; Escape closes only the list; nothing is kept in
// browser storage.

const editor = (target: Page) => target.locator(".ledger-invoice-editor");
const field = (target: Page, key: string) =>
  editor(target)
    .getByLabel(label(`desktop.ledger.invoices.field.${key}`), { exact: true })
    .and(editor(target).locator("input, select, textarea"));
const list = (target: Page) => target.getByRole("listbox");

async function newIssued(target: Page) {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.invoices") })
    .click();
  const section = target.locator(".ledger-invoices");
  await expect(section.getByRole("grid")).toBeVisible();
  await target.locator(".pane-docs .pane-head .ledger-add").click();
  await expect(editor(target)).toBeVisible();
  await editor(target)
    .getByRole("radio", {
      name: label("desktop.ledger.invoices.kind_choice.issued"),
    })
    .click();
}

/** The party the catalogue holds that the test types the start of. */
async function aParty(target: Page) {
  const name = field(target, "counterparty_name");
  await name.fill("a");
  await expect(list(target).getByRole("option").first()).toBeVisible();
  const first = list(target).getByRole("option").first();
  const words = (await first.innerText()).split("\n");
  await name.fill(words[0]!.slice(0, 4));
  await expect(first).toBeVisible();
  return { typed: words[0]!.slice(0, 4), name: words[0]! };
}

test("a pick fills the empty tax id and country", async ({ page: target }) => {
  await newIssued(target);
  const party = await aParty(target);
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Enter");
  await expect(field(target, "counterparty_name")).toHaveValue(party.name);
  await expect(list(target)).toHaveCount(0);
  await expect(field(target, "counterparty_name")).toBeFocused();
  await expect(field(target, "counterparty_tax_id")).not.toHaveValue("");
  await field(target, "counterparty_country").focus();
  await expect(field(target, "counterparty_country")).not.toHaveValue("");
});

test("a pick leaves a tax id already typed", async ({ page: target }) => {
  await newIssued(target);
  await field(target, "counterparty_tax_id").fill("X1234567L");
  await field(target, "counterparty_name").focus();
  const party = await aParty(target);
  await list(target).getByRole("option").first().click();
  await expect(field(target, "counterparty_name")).toHaveValue(party.name);
  await expect(field(target, "counterparty_tax_id")).toHaveValue("X1234567L");
  // The press on the option left focus in the field.
  await expect(field(target, "counterparty_name")).toBeFocused();
});

test("Enter and Tab keep what was typed until an option is highlighted", async ({
  page: target,
}) => {
  await newIssued(target);
  const party = await aParty(target);
  await target.keyboard.press("Tab");
  await expect(field(target, "counterparty_name")).toHaveValue(party.typed);
  await expect(field(target, "counterparty_tax_id")).toHaveValue("");
  await expect(list(target)).toHaveCount(0);
});

test("Tab with a highlight chooses and moves on", async ({ page: target }) => {
  await newIssued(target);
  const party = await aParty(target);
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Tab");
  await expect(field(target, "counterparty_name")).toHaveValue(party.name);
  await expect(field(target, "counterparty_tax_id")).toBeFocused();
});

test("Escape closes the list and leaves the editor open", async ({
  page: target,
}) => {
  await newIssued(target);
  const party = await aParty(target);
  await target.keyboard.press("Escape");
  await expect(list(target)).toHaveCount(0);
  await expect(editor(target)).toBeVisible();
  await expect(field(target, "counterparty_name")).toHaveValue(party.typed);
  await expect(field(target, "counterparty_name")).toBeFocused();
});

test("the field names its list and which option is active", async ({
  page: target,
}) => {
  await newIssued(target);
  await aParty(target);
  const name = field(target, "counterparty_name");
  await expect(name).toHaveAttribute("role", "combobox");
  await expect(name).toHaveAttribute("aria-expanded", "true");
  await expect(name).not.toHaveAttribute("aria-activedescendant", /./);
  await target.keyboard.press("ArrowDown");
  const active = await name.getAttribute("aria-activedescendant");
  await expect(target.locator(`[id="${active}"]`)).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(list(target)).toHaveAccessibleName(
    label("desktop.ledger.invoices.field.counterparty_name"),
  );
});

test("nothing typed or offered is kept in browser storage", async ({
  page: target,
}) => {
  await newIssued(target);
  const party = await aParty(target);
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Enter");
  const taxId = await field(target, "counterparty_tax_id").inputValue();
  const stored = await target.evaluate(async () => {
    const all = (area: Storage) =>
      Array.from({ length: area.length }, (_, at) => {
        const key = area.key(at)!;
        return `${key}=${area.getItem(key)}`;
      });
    const databases = await indexedDB.databases();
    return {
      text: [...all(localStorage), ...all(sessionStorage)].join("\n"),
      databases: databases.map((database) => database.name),
    };
  });
  expect(stored.text).not.toContain(party.name);
  expect(stored.text).not.toContain(taxId);
  expect(stored.databases).toEqual([]);
});

test("the browser is told to remember no field of the invoice", async ({
  page: target,
}) => {
  await newIssued(target);
  const inputs = editor(target).locator("input:not([type=checkbox])");
  const count = await inputs.count();
  expect(count).toBeGreaterThan(3);
  for (let at = 0; at < count; at += 1)
    await expect(inputs.nth(at)).toHaveAttribute("autocomplete", "off");
});

const grid = (target: Page) => target.locator(".ledger-page").getByRole("grid");
const cellEditor = (target: Page) => target.locator(".ledger-cell-editor");

async function openGrid(target: Page) {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(grid(target).locator("[data-kind=data]").first()).toBeVisible();
}

/** Opens the first row's cell of `column` and types `text` in it. */
async function typeInCell(target: Page, column: string, text: string) {
  const cell = grid(target)
    .locator("[data-kind=data]")
    .first()
    .locator(`[data-column=${column}]`);
  await cell.click();
  await target.keyboard.press("Enter");
  await expect(cellEditor(target)).toBeVisible();
  await cellEditor(target).fill(text);
  return cell;
}

test("a press on a grid cell's option commits the pick, not what was typed", async ({
  page: target,
}) => {
  await openGrid(target);
  const other = await grid(target)
    .locator("[data-kind=data]")
    .nth(1)
    .locator("[data-column=counterparty]")
    .innerText();
  const cell = await typeInCell(target, "counterparty", other.slice(0, 4));
  const option = list(target)
    .getByRole("option")
    .filter({ hasText: other })
    .first();
  await expect(option).toBeVisible();
  await option.click();
  await expect(cellEditor(target)).toHaveCount(0);
  await expect(cell).toContainText(other);
});

test("in a grid cell, Enter keeps what was typed and Escape closes only the list", async ({
  page: target,
}) => {
  await openGrid(target);
  const other = await grid(target)
    .locator("[data-kind=data]")
    .nth(1)
    .locator("[data-column=counterparty]")
    .innerText();
  const typed = other.slice(0, 4);
  const cell = await typeInCell(target, "counterparty", typed);
  await expect(list(target).getByRole("option").first()).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(list(target)).toHaveCount(0);
  await expect(cellEditor(target)).toBeVisible();
  await expect(cellEditor(target)).toHaveValue(typed);
  await target.keyboard.press("Enter");
  await expect(cellEditor(target)).toHaveCount(0);
  await expect(cell).toContainText(typed);
});

test("signing in to another profile holds nothing from the last one", async ({
  page: target,
}) => {
  const catalogueReads = () =>
    target.evaluate(
      () =>
        (
          (window as unknown as { __scenarioHostCalls?: string[] })
            .__scenarioHostCalls ?? []
        ).filter((call) => call === "ledger ledger.invoice.list").length,
    );
  await openGrid(target);
  const other = await grid(target)
    .locator("[data-kind=data]")
    .nth(1)
    .locator("[data-column=counterparty]")
    .innerText();
  await typeInCell(target, "counterparty", other.slice(0, 4));
  await expect(list(target).getByRole("option").first()).toBeVisible();
  await expect.poll(catalogueReads).toBeGreaterThan(0);
  await target.keyboard.press("Escape");
  await target.keyboard.press("Escape");

  const menu = target.locator(".account-menu");
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await menu
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(list(target)).toHaveCount(0);
  await menu
    .getByRole("menuitem", {
      name: label("desktop.signin.submit"),
      exact: true,
    })
    .click();
  const signIn = target.locator(".sign-in");
  const profile = signIn.getByLabel(label("desktop.signin.profile"), {
    exact: true,
  });
  const current = await profile.inputValue();
  const others = await profile
    .locator("option")
    .evaluateAll(
      (options, held) =>
        options
          .map((option) => (option as HTMLOptionElement).value)
          .filter((value) => value !== held),
      current,
    );
  await profile.selectOption(others[0]!);
  await target.locator("#profile-password").fill("anything");
  await signIn
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(grid(target)).toBeVisible();

  // The new page asks its own reader again before it can offer anything.
  const before = await catalogueReads();
  await typeInCell(target, "counterparty", other.slice(0, 4));
  await expect.poll(catalogueReads).toBe(before + 1);
});
