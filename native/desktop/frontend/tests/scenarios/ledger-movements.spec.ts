import { expect, test, type Locator, type Page } from "@playwright/test";
import { LEDGER_PAGE_SIZE } from "../../src/shell/ledgerWindow";
import { label } from "../support/strings";

// The Movements section over the scenario's ledger: the period read in
// pages, the readiness strip whose every pill and chip filters exactly what
// it counts, the toolbar's search, filters, views, grouping, sorting and
// columns, the selection, and the keys. What it stages is checked by the
// staging scenarios; here the grid shows stored values only.

const open = (target: Page, extra = "") =>
  target.goto(`/scenarios.html?scenario=ledger&latency=0&bar=off${extra}`);

const page = (target: Page) => target.locator(".ledger-page");
const head = (target: Page) => target.locator(".pane-docs .pane-head");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const sections = (target: Page) => grid(target).locator("[data-kind=section]");
const count = (target: Page) => page(target).locator(".ledger-count");
const pill = (target: Page, kind: string) =>
  page(target).locator(`.ledger-readiness [data-readiness=${kind}] button`);

async function openLedger(target: Page, extra = "") {
  await open(target, extra);
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
}

async function choosePeriod(target: Page, year: number, code: string) {
  await head(target).locator(".ledger-period").click();
  const periods = target.getByRole("dialog", {
    name: label("desktop.ledger.period.choose"),
  });
  const shown = periods.locator("[aria-live=polite]");
  for (let guard = 0; guard < 40; guard += 1) {
    const at = Number(await shown.textContent());
    if (at === year) break;
    await periods
      .getByRole("button", {
        name: label(
          at > year
            ? "desktop.ledger.period.year_previous"
            : "desktop.ledger.period.year_next",
        ),
        exact: true,
      })
      .click();
  }
  await periods
    .getByRole("group", {
      name: label("desktop.ledger.period.of_year", { year }),
    })
    .getByRole("button", {
      name: code === "0A" ? label("desktop.ledger.period.year") : code,
      exact: true,
    })
    .click();
  await expect(periods).toBeHidden();
}

/** What the toolbar says is shown: "8 of 40 movements". */
async function shownOf(
  target: Page,
): Promise<{ shown: number; total: number }> {
  const text = ((await count(target).textContent()) ?? "").split(" · ")[0]!;
  const numbers = [...text.matchAll(/\d[\d,]*/g)].map((found) =>
    Number(found[0].replace(/,/g, "")),
  );
  return numbers.length === 2
    ? { shown: numbers[0]!, total: numbers[1]! }
    : { shown: numbers[0]!, total: numbers[0]! };
}
const pillCount = async (button: Locator) =>
  Number(await button.locator("span[aria-hidden=true]").first().textContent());

test("a period is read whole, in pages, before the grid draws it", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "0A");
  await expect(count(target)).toHaveText(/\d/);
  const { shown, total } = await shownOf(target);
  // More than one page of the list: the window joined them.
  expect(total).toBeGreaterThan(LEDGER_PAGE_SIZE);
  expect(shown).toBe(total);
  await expect(grid(target)).toHaveAttribute(
    "aria-rowcount",
    String(total + 1),
  );
  // Windowed: only what is in view is in the document.
  expect(await dataRows(target).count()).toBeLessThan(80);
});

test("each readiness pill and reason chip filters exactly what it counts", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "0A");
  const strip = page(target).locator(".ledger-readiness");
  await expect(strip.locator("[data-readiness]")).not.toHaveCount(0);
  await expect(strip.locator("[data-readiness=unknown]")).toHaveCount(0);
  let checked = 0;
  for (const kind of ["issues", "to_classify", "no_rate"]) {
    const button = pill(target, kind);
    if ((await button.count()) === 0) continue;
    checked += 1;
    const counted = await pillCount(button);
    await button.click();
    await expect(button).toHaveAttribute("aria-pressed", "true");
    await expect.poll(async () => (await shownOf(target)).shown).toBe(counted);
    // The name says it in words, with no glyph.
    expect(await button.textContent()).not.toMatch(/[⚠○⊘✓◌]/u);
    await button.click();
    await expect(button).toHaveAttribute("aria-pressed", "false");
  }
  expect(checked).toBeGreaterThan(0);
  const chips = page(target).locator(".ledger-reasons [data-reason] button");
  for (const chip of await chips.all()) {
    const counted = Number(await chip.locator(".tabular-nums").textContent());
    await chip.click();
    await expect.poll(async () => (await shownOf(target)).shown).toBe(counted);
    await chip.click();
  }
});

test("a reason chip leads to the fix: its movements, its column and the first one chosen", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "0A");
  const chip = page(target).locator(
    ".ledger-reasons [data-reason=missing_category] button",
  );
  await expect(chip).toBeVisible();
  // A selection made before is replaced.
  await dataRows(target).nth(2).click();
  await dataRows(target)
    .nth(4)
    .click({ modifiers: ["Control"] });
  await chip.click();
  await expect(count(target)).toContainText(
    label("desktop.ledger.selected", { count: 1 }),
  );
  const first = dataRows(target).first();
  await expect(first).toHaveAttribute("aria-selected", "true");
  const category = first.locator("[data-column=category]");
  await expect(category).toBeFocused();
  // The missing cell says so in words, and with its cell.
  await expect(category).toContainText(label("desktop.ledger.missing"));
  const note = await category.getAttribute("aria-describedby");
  expect(note).toBeTruthy();
  const said = await target.evaluate(
    (ids) =>
      ids
        .split(" ")
        .map((id) => document.getElementById(id)?.textContent ?? "")
        .join(" "),
    note!,
  );
  expect(said).toContain(
    label("desktop.ledger.reason_detail.missing_category"),
  );
});

test("the search matches words and figures, and says what other periods hold", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  const search = page(target).getByRole("searchbox", {
    name: label("desktop.ledger.search.label"),
  });
  await search.fill("farmacia");
  const here = (await shownOf(target)).shown;
  expect(here).toBeGreaterThan(0);
  for (const description of await dataRows(target)
    .locator("[data-column=description]")
    .allTextContents())
    expect(description.toLowerCase()).toContain("farmacia");
  const elsewhere = page(target).locator(".ledger-elsewhere");
  await expect(elsewhere).toBeVisible();
  const more = Number(/\d+/.exec((await elsewhere.textContent()) ?? "")![0]);
  expect(more).toBeGreaterThan(0);
  await elsewhere
    .getByRole("button", { name: label("desktop.ledger.search.show") })
    .click();
  await expect(head(target).locator(".ledger-period")).toHaveText(
    label("desktop.ledger.period.all"),
  );
  await expect
    .poll(async () => (await shownOf(target)).shown)
    .toBe(here + more);
  // Escape clears the search, and the search is not kept in storage.
  await search.press("Escape");
  await expect(search).toHaveValue("");
  const stored = await target.evaluate(() => JSON.stringify(localStorage));
  expect(stored.toLowerCase()).not.toContain("farmacia");
});

test("the filters narrow the grid and show as chips that take them off", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "0A");
  const all = (await shownOf(target)).total;
  await page(target)
    .getByRole("button", { name: label("desktop.ledger.filters.title") })
    .click();
  const filters = target.locator(".ledger-filters");
  await filters
    .getByRole("button", {
      name: label("desktop.ledger.direction.incoming"),
      exact: true,
    })
    .click();
  await target.keyboard.press("Escape");
  const incoming = (await shownOf(target)).shown;
  expect(incoming).toBeGreaterThan(0);
  expect(incoming).toBeLessThan(all);
  for (const cell of await dataRows(target)
    .locator("[data-column=direction]")
    .allTextContents())
    expect(cell).toContain(label("desktop.ledger.direction.incoming"));
  const chip = page(target).locator(".ledger-chips [data-slot=filter-chip]");
  await expect(chip).toHaveCount(1);
  await chip
    .getByRole("button", {
      name: label("desktop.ledger.filters.remove", {
        filter: label("desktop.ledger.direction.incoming"),
      }),
    })
    .click();
  await expect(chip).toHaveCount(0);
  await expect.poll(async () => (await shownOf(target)).shown).toBe(all);

  // The product's own filter: one account's movements, read from the ledger.
  await page(target)
    .getByRole("button", { name: label("desktop.ledger.filters.title") })
    .click();
  const account = filters.getByLabel(label("desktop.ledger.filters.account"));
  await expect(account.locator("option")).toHaveCount(3);
  await account.selectOption({ index: 1 });
  await target.keyboard.press("Escape");
  await expect
    .poll(async () => (await shownOf(target)).shown)
    .toBeLessThan(all);
  await expect(page(target).locator(".ledger-chips")).toBeVisible();
});

test("grouping by counterparty heads each group with its count, sums and actions", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  await page(target)
    .getByRole("button", {
      name: label("desktop.ledger.view.named", {
        view: label("desktop.ledger.view.all"),
      }),
    })
    .click();
  await target
    .getByRole("menuitemradio", {
      name: label("desktop.ledger.view.to_classify"),
    })
    .click();
  await target.keyboard.press("Escape");
  await expect(sections(target)).not.toHaveCount(0);
  const header = sections(target).first();
  await expect(header).toContainText(
    label("desktop.ledger.group.count", { count: 1 }).replace("1", ""),
  );
  await expect(header).toContainText(/(Out|In) \d/);
  // The actions are one Classify menu and a menu of the rest.
  await expect(
    header.getByRole("button", {
      name: label("desktop.ledger.group.classify"),
      exact: true,
    }),
  ).toBeVisible();
  await header
    .getByRole("button", { name: label("desktop.ledger.group.more") })
    .click();
  const more = target.getByRole("menu");
  for (const item of [
    `${label("desktop.ledger.group.category")}…`,
    `${label("desktop.ledger.group.make_rule")}…`,
  ])
    await expect(
      more.getByRole("menuitem", { name: item, exact: true }),
    ).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(more).toHaveCount(0);
  // A group folds and opens again by its header.
  const before = await dataRows(target).count();
  await header
    .locator("[role=gridcell]")
    .first()
    .click({ position: { x: 8, y: 8 } });
  await expect(dataRows(target)).toHaveCount(before - 1);
  // The fold says it is folded; the action menus are not folds.
  await expect(
    header.locator("[aria-expanded=false]:not([aria-haspopup])"),
  ).toHaveCount(1);
  // The view and its grouping are kept as presentation.
  await expect
    .poll(() =>
      target.evaluate(() => {
        const view = JSON.parse(
          localStorage.getItem("cadrumo-shell-layout") ?? "{}",
        ).layout?.ledgerView;
        return view ? `${view.savedView} ${view.groupBy}` : "";
      }),
    )
    .toBe("to_classify counterparty");
  // A group's Personal stages through the one classify command.
  await header
    .getByRole("button", {
      name: label("desktop.ledger.group.classify"),
      exact: true,
    })
    .click();
  await target
    .getByRole("menuitem", {
      name: label("desktop.ledger.group.personal"),
      exact: true,
    })
    .click();
  await expect(page(target).locator(".ledger-toast")).toContainText(
    label("desktop.ledger.classification.personal"),
  );
});

test("choosing a grouping closes the Group menu", async ({ page: target }) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  await page(target)
    .getByRole("button", { name: label("desktop.ledger.group.title") })
    .click();
  await target
    .getByRole("menuitemradio", {
      name: label("desktop.ledger.group.counterparty"),
    })
    .click();
  await expect(target.getByRole("menu")).toHaveCount(0);
  await expect(sections(target)).not.toHaveCount(0);
});

test("a transfer's direction is its glyph, with the word in its name and tooltip", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  const transfer = dataRows(target)
    .filter({
      has: target.locator("[data-column=description]", {
        hasText: "TRASPASO",
      }),
    })
    .first()
    .locator("[data-column=direction]");
  const word = label("desktop.ledger.direction.internal_transfer");
  await expect(transfer.locator(".sr-only")).toHaveText(word);
  // Nothing of the word is drawn to be cut short.
  await expect(transfer.locator(".truncate")).toHaveCount(0);
  await transfer.locator("[data-slot=tooltip-trigger]").hover();
  await expect(target.getByRole("tooltip")).toHaveText(word);
});

test("text cut short shows whole in the grid's tooltip, and a click on it still selects its row", async ({
  page: target,
}) => {
  await openLedger(target);
  const cut = dataRows(target)
    .locator("[data-column=description] [data-slot=data-grid-text]")
    .filter({ hasText: "SOFTNUBE" })
    .first();
  const whole = (await cut.textContent()) ?? "";
  expect(
    await cut.evaluate((element) => element.scrollWidth > element.clientWidth),
  ).toBe(true);
  await cut.hover();
  await expect(target.getByRole("tooltip")).toHaveText(whole);
  // Escape puts it away until the pointer comes back.
  await target.keyboard.press("Escape");
  await expect(target.getByRole("tooltip")).toHaveCount(0);
  // The press lands on the same element the pointer entered.
  await cut.click();
  await expect(
    dataRows(target).filter({ hasText: "SOFTNUBE" }).first(),
  ).toHaveAttribute("aria-selected", "true");
});

test("sorting by a column header orders the stored figures", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  const amount = grid(target).getByRole("columnheader", {
    name: label("desktop.ledger.column.amount"),
  });
  await amount.click();
  await expect(amount).toHaveAttribute("aria-sort", "ascending");
  const figures = async () =>
    (await dataRows(target).locator("[data-column=amount]").allTextContents())
      .slice(0, 8)
      .map((text) => Number(text.replace(/[^\d.]/g, "")));
  const ascending = await figures();
  expect([...ascending].sort((a, b) => a - b)).toEqual(ascending);
  await amount.click();
  await expect(amount).toHaveAttribute("aria-sort", "descending");
  const descending = await figures();
  expect([...descending].sort((a, b) => b - a)).toEqual(descending);
});

test("the columns are chosen and ordered, and kept without a value", async ({
  page: target,
}) => {
  await openLedger(target);
  await page(target)
    .getByRole("button", {
      name: new RegExp(`^${label("desktop.ledger.columns.title")}`),
    })
    .click();
  const chooser = target.locator(".ledger-columns");
  await chooser
    .getByRole("radio", { name: label("desktop.ledger.columns.preset.iva") })
    .click();
  await expect(
    grid(target).getByRole("columnheader", {
      name: label("desktop.ledger.column.iva_rate"),
    }),
  ).toBeVisible();
  await chooser
    .locator("[data-column=counterparty]")
    .getByRole("checkbox")
    .click();
  await chooser
    .getByRole("button", {
      name: label("desktop.ledger.columns.move_up", {
        column: label("desktop.ledger.column.category"),
      }),
    })
    .click();
  await target.keyboard.press("Escape");
  const headers = async () =>
    grid(target).getByRole("columnheader").allTextContents();
  const shown = await headers();
  expect(shown).not.toContain(label("desktop.ledger.column.counterparty"));
  expect(shown.indexOf(label("desktop.ledger.column.category"))).toBeLessThan(
    shown.indexOf(label("desktop.ledger.column.classification")),
  );
  await page(target)
    .getByRole("button", { name: label("desktop.ledger.density.comfortable") })
    .click();
  await target.reload();
  await expect(grid(target)).toBeVisible();
  expect(await headers()).toEqual(shown);
  await expect(grid(target).locator("..")).toHaveAttribute(
    "data-density",
    "comfortable",
  );
  await expect
    .poll(() =>
      target.evaluate(
        () =>
          JSON.parse(localStorage.getItem("cadrumo-shell-layout") ?? "{}")
            .layout?.ledgerView?.density,
      ),
    )
    .toBe("comfortable");
  const stored = await target.evaluate(
    () => localStorage.getItem("cadrumo-shell-layout") ?? "",
  );
  const view = JSON.parse(stored).layout.ledgerView;
  expect(view.columns.hidden).toContain("counterparty");
  expect(view.density).toBe("comfortable");
  // Ids and sizes only: no description, amount or counterparty.
  for (const value of ["PAPELERIA", "Papelería", "77.44", "FARMACIA", "2026-1"])
    expect(stored).not.toContain(value);
});

test("the header box selects what is shown, and a hidden selection is said", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  const box = grid(target).getByRole("checkbox", {
    name: label("desktop.ledger.select.shown"),
  });
  await box.click();
  const total = (await shownOf(target)).total;
  await expect(count(target)).toContainText(
    label("desktop.ledger.selected", { count: total }),
  );
  // A search hides some of the selection: the page says so before any
  // command acts on it.
  const search = page(target).getByRole("searchbox", {
    name: label("desktop.ledger.search.label"),
  });
  await search.fill("farmacia");
  const shown = (await shownOf(target)).shown;
  const banner = page(target).locator(".ledger-hidden-selection");
  const hidden = label("desktop.ledger.selection.hidden", {
    hidden: total - shown,
    selected: total,
  });
  await expect(banner).toContainText(hidden);
  // Nothing classifies what cannot be seen.
  await search.press("ArrowDown");
  await expect(target.locator("[role=gridcell]:focus")).toHaveCount(1);
  await target.keyboard.press("Alt+KeyB");
  await expect(page(target).locator(".ledger-toast")).toContainText(hidden);
  await expect(target.locator(".ledger-classify")).toHaveCount(0);
  await banner
    .getByRole("button", {
      name: label("desktop.ledger.selection.keep_visible"),
    })
    .click();
  await expect(banner).toHaveCount(0);
  await expect(count(target)).toContainText(
    label("desktop.ledger.selected", { count: shown }),
  );
  // The header box with Ctrl adds the shown movements to the selection.
  await search.fill("");
  await dataRows(target).first().locator("[data-column=description]").click();
  await search.fill("farmacia");
  await box.click({ modifiers: ["Control"] });
  await search.fill("");
  await expect(count(target)).toContainText(
    label("desktop.ledger.selected", { count: shown + 1 }),
  );
});

test("the grid's keys: typing never runs a command, Alt+B and F8 do, shell chords pass", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  await dataRows(target).first().locator("[data-column=description]").click();
  // A bare letter is typing: nothing on the page takes it.
  for (const key of ["b", "p", "m", "n", "/"]) await target.keyboard.press(key);
  await expect(target.locator(".ledger-classify")).toHaveCount(0);
  await expect(target.locator(".palette")).toHaveCount(0);
  // It opened the cell's editor, which holds what was typed.
  await expect(target.locator(".ledger-cell-editor")).toHaveValue("bpmn/");
  await target.keyboard.press("Escape");
  await expect(target.locator(".ledger-cell-editor")).toHaveCount(0);
  await target.keyboard.press("Alt+KeyB");
  const dialog = target.locator(".ledger-classify");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText(label("desktop.ledger.classify.category"));
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);

  // F8 goes to the next movement readiness found something on.
  await choosePeriod(target, 2026, "0A");
  await dataRows(target).first().locator("[data-column=description]").click();
  await target.keyboard.press("F8");
  const focused = target.locator("[role=gridcell]:focus");
  await expect(focused).toHaveCount(1);
  const row = focused.locator("xpath=..");
  const status = await row.getAttribute("data-key");
  expect(status).toBeTruthy();
  await expect(row).toHaveAttribute("aria-selected", "true");

  // The shell's chords are the shell's, from inside the grid too.
  await target.keyboard.press("Control+KeyK");
  await expect(target.locator(".palette")).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(target.locator(".palette")).toBeHidden();
  await dataRows(target).first().locator("[data-column=description]").click();
  await target.keyboard.press("F6");
  await expect(target.locator("[role=gridcell]:focus")).toHaveCount(0);
});

const rowWith = (target: Page, text: string) =>
  dataRows(target)
    .filter({
      has: target.locator("[data-column=description]", { hasText: text }),
    })
    .first();
const toast = (target: Page) => page(target).locator(".ledger-toast");
const classify = (target: Page) => target.locator(".ledger-classify");

test("Business on income asks for no expense category, and on both says which is which", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  // Income alone is staged at once: it takes no spending category.
  await rowWith(target, "FRA 2026-058").locator("[data-column=status]").click();
  await target.keyboard.press("Alt+KeyB");
  await expect(classify(target)).toHaveCount(0);
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.classify.staged", {
      classification: label("desktop.ledger.classification.business"),
      count: 1,
    }),
  );
  // An expense and an income: the category is asked for the expense only.
  await rowWith(target, "PAPELERIA TRAZO")
    .locator("[data-column=status]")
    .click();
  await rowWith(target, "FRA 2026-058")
    .locator("[data-column=status]")
    .click({ modifiers: ["Control"] });
  await target.keyboard.press("Alt+KeyB");
  await expect(classify(target).getByRole("heading")).toHaveText(
    label("desktop.ledger.classify.title_business_split", {
      expenses: 1,
      income: 1,
    }),
  );
  await expect(classify(target)).toContainText(
    label("desktop.ledger.classify.expense_category", { count: 1 }),
  );
  await expect(classify(target)).toContainText(
    label("desktop.ledger.classify.income_no_category", { count: 1 }),
  );
  await target.keyboard.press("Escape");
  await expect(classify(target)).toHaveCount(0);
  await expect(target.locator("[role=gridcell]:focus")).toHaveCount(1);
});

test("Mixed asks its share and a category a share applies to; Enter stages, and focus returns", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  await rowWith(target, "RECIBO TELEFONIA")
    .locator("[data-column=description]")
    .click();
  await target.keyboard.press("Alt+KeyM");
  const dialog = classify(target);
  await expect(dialog).toBeVisible();
  await dialog.getByLabel(label("desktop.ledger.classify.share")).fill("30");
  await dialog.locator(".ledger-classify-category").click();
  const list = target.locator("[data-slot=combobox]");
  await expect(list).toContainText(
    label("desktop.ledger.classify.share_categories"),
  );
  // A category with no business-use share is not offered.
  await expect(
    list.getByRole("option", {
      name: label("desktop.ledger.category.software_suscripcion"),
    }),
  ).toHaveCount(0);
  await target.keyboard.type(label("desktop.ledger.category.telefonia_movil"));
  await target.keyboard.press("Enter");
  await expect(list).toBeHidden();
  // With both filled in, Enter stages rather than opening the list again.
  await target.keyboard.press("Enter");
  await expect(dialog).toHaveCount(0);
  await expect(toast(target)).toContainText(
    label("desktop.ledger.category.telefonia_movil"),
  );
  await expect(toast(target)).toContainText("30%");
  const focused = target.locator("[role=gridcell]:focus");
  await expect(focused).toHaveCount(1);
  await expect(focused.locator("xpath=..")).toContainText("RECIBO TELEFONIA");
});

test("the classify chords work after a checkbox selection, and Shift+Space then Shift+arrows select rows", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  await dataRows(target).nth(0).locator("input[type=checkbox]").click();
  await dataRows(target)
    .nth(2)
    .locator("input[type=checkbox]")
    .click({ modifiers: ["Shift"] });
  await expect(count(target)).toContainText(
    label("desktop.ledger.selected", { count: 3 }),
  );
  // Focus sits on the checkbox: the chord is still the page's.
  await target.keyboard.press("Alt+KeyB");
  await expect(classify(target)).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(classify(target)).toHaveCount(0);

  await dataRows(target).nth(0).locator("[data-column=description]").click();
  await target.keyboard.press("Shift+Space");
  for (let step = 0; step < 3; step += 1)
    await target.keyboard.press("Shift+ArrowDown");
  await expect(count(target)).toContainText(
    label("desktop.ledger.selected", { count: 4 }),
  );
});

test("the classify chords work from the Ledger header, and never in a text field", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  await dataRows(target).nth(0).locator("input[type=checkbox]").click();
  for (const control of [
    head(target).locator(".ledger-period"),
    head(target).getByRole("tab").first(),
  ]) {
    await control.focus();
    await target.keyboard.press("Alt+KeyB");
    await expect(classify(target)).toBeVisible();
    await target.keyboard.press("Escape");
    await expect(classify(target)).toHaveCount(0);
  }
  const search = page(target).getByRole("searchbox", {
    name: label("desktop.ledger.search.label"),
  });
  await search.focus();
  await target.keyboard.press("Alt+KeyB");
  await expect(classify(target)).toHaveCount(0);
});

test("a cell range over other rows than the selection is said, and can become it", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  await rowWith(target, "PAPELERIA TRAZO")
    .locator("[data-column=description]")
    .click();
  await target.keyboard.press("Shift+ArrowDown");
  await target.keyboard.press("Shift+ArrowDown");
  await target.keyboard.press("Alt+KeyB");
  const dialog = classify(target);
  await expect(dialog.locator(".ledger-classify-range")).toContainText(
    label("desktop.ledger.classify.range_differs", { selected: 1, range: 3 }),
  );
  await dialog.locator(".ledger-classify-select-range").click();
  await expect(count(target)).toContainText(
    label("desktop.ledger.selected", { count: 3 }),
  );
  await expect(dialog.locator(".ledger-classify-range")).toHaveCount(0);
  await expect(dialog.locator(".ledger-classify-stage")).toHaveText(
    label("desktop.ledger.classify.stage", { count: 3 }),
  );
});

test("an imported likely duplicate is marked, counted, and offered its archive", async ({
  page: target,
}) => {
  await openLedger(target);
  await head(target).locator(".ledger-period").click();
  await target.locator(".ledger-period-all").click();
  const chip = page(target).locator(".ledger-duplicates");
  await expect(chip).toBeVisible();
  const counted = Number(await chip.locator(".tabular-nums").textContent());
  expect(counted).toBeGreaterThan(0);
  await chip.click();
  await expect(chip).toHaveAttribute("aria-pressed", "true");
  await expect.poll(async () => (await shownOf(target)).shown).toBe(counted);
  const row = dataRows(target).first();
  const mark = row.locator("[data-column=status] [data-duplicate]");
  await expect(mark).toHaveCount(1);
  await expect(mark.locator(".sr-only")).toHaveText(
    label("desktop.ledger.import_issue.duplicate"),
  );
  await row.locator("[data-column=description]").click({ button: "right" });
  await target
    .getByRole("menuitem", {
      name: `${label("desktop.ledger.duplicate.archive")}…`,
    })
    .click();
  const dialog = target.locator(".ledger-action-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("textbox")).toHaveValue(
    label("desktop.ledger.import_issue.duplicate"),
  );
  await target.keyboard.press("Escape");
  await expect(target.locator("[role=gridcell]:focus")).toHaveCount(1);
});

test("compact status cells draw a state as its glyph, named, and widen for the marks they carry", async ({
  page: target,
}) => {
  await openLedger(target);
  await head(target).locator(".ledger-period").click();
  await target.locator(".ledger-period-all").click();
  const rem = await target.evaluate(() =>
    parseFloat(getComputedStyle(document.documentElement).fontSize),
  );
  const statusHeader = grid(target).getByRole("columnheader", {
    name: label("desktop.ledger.column.status"),
  });
  // One kind of mark, the duplicate flag: one glyph wider than 2.75rem.
  await expect
    .poll(async () => Math.round((await statusHeader.boundingBox())!.width))
    .toBe(Math.round(4 * rem));
  // The header's glyph names the column; it is not the Done glyph.
  const done = grid(target).locator("[data-status=done] svg").first();
  expect(await statusHeader.locator("svg").innerHTML()).not.toBe(
    await done.innerHTML(),
  );

  // Archive a movement: its state then shows as a glyph, whole.
  await choosePeriod(target, 2026, "4T");
  const description = "PAPELERIA TRAZO";
  await rowWith(target, description).locator("[data-column=status]").click();
  await target.keyboard.press("Alt+KeyI");
  await target
    .locator("aside.ledger-panel")
    .getByRole("button", { name: label("desktop.ledger.inspector.actions") })
    .click();
  await target
    .getByRole("menuitem", {
      name: `${label("desktop.ledger.inspector.action.archive")}…`,
    })
    .click();
  const dialog = target.locator(".ledger-action-dialog");
  await dialog.getByRole("textbox").fill("Test");
  await dialog
    .getByRole("button", { name: label("desktop.ledger.inspector.stage") })
    .click();
  await target.locator(".ledger-tray .ledger-tray-review").click();
  const review = target.locator(".ledger-review");
  await review.locator(".ledger-apply-save").click();
  await expect(review.locator(".ledger-apply-done")).toBeVisible({
    timeout: 20_000,
  });
  await target.keyboard.press("Escape");
  const archived = rowWith(target, description);
  const mark = archived.locator("[data-column=status] [data-lifecycle]");
  await expect(mark).toHaveAttribute("data-lifecycle", "ARCHIVED");
  await expect(mark.locator(".sr-only")).toHaveText(
    label("desktop.ledger.lifecycle.archived"),
  );
  const cell = (await archived.locator("[data-column=status]").boundingBox())!;
  const glyph = (await mark.boundingBox())!;
  expect(glyph.x + glyph.width).toBeLessThanOrEqual(cell.x + cell.width);
});

test("the tooltip of a cut-short cell goes away as the grid scrolls", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  const cell = rowWith(target, "SOFTNUBE IRELAND").locator(
    "[data-column=description]",
  );
  await cell.click();
  const tip = target.getByRole("tooltip");
  await expect(tip).toContainText("SOFTNUBE IRELAND");
  // The focused cell keeps its focus; its tip would float over other rows.
  await grid(target).evaluate((element) => {
    element.scrollTop += 120;
  });
  await expect(tip).toHaveCount(0);
  await expect(cell).toBeFocused();
});

test("a failed read of the duplicate flags says so instead of marking none", async ({
  page: target,
}) => {
  await openLedger(target);
  // Over all periods the duplicates read asks for the flag alone. The page
  // may read it more than once as the window settles; each read fails.
  await target.evaluate(() =>
    window.__scenarioLedger!.nextReads("ledger.list", 20, {
      filters: ["issue=duplicate"],
    }),
  );
  await head(target).locator(".ledger-period").click();
  await target.locator(".ledger-period-all").click();
  await expect(dataRows(target).first()).toBeVisible();
  await expect(page(target).locator(".ledger-duplicates-failed")).toHaveText(
    label("desktop.ledger.duplicate.failed"),
  );
  await expect(page(target).locator(".ledger-duplicates")).toHaveCount(0);
});

test("where the review preset does not fit it gives up Group, and a cue names the columns scrolled away", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1100, height: 800 });
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  const header = (name: string) =>
    grid(target).getByRole("columnheader", { name, exact: true });
  await expect(header(label("desktop.ledger.column.category"))).toHaveCount(1);
  await expect(header(label("desktop.ledger.column.group_label"))).toHaveCount(
    0,
  );
  // The columns menu says Group is hidden, and showing it there draws it.
  await page(target)
    .getByRole("button", {
      name: new RegExp(`^${label("desktop.ledger.columns.title")}`),
    })
    .click();
  const group = target
    .locator(".ledger-columns li[data-column=group_label]")
    .getByRole("checkbox");
  await expect(group).not.toBeChecked();
  await group.check();
  await target.keyboard.press("Escape");
  await expect(header(label("desktop.ledger.column.group_label"))).toHaveCount(
    1,
  );
  // A wider preset scrolls under the pinned amount: the header says how
  // many columns are there, and takes the person to them.
  await page(target)
    .getByRole("button", {
      name: new RegExp(`^${label("desktop.ledger.columns.title")}`),
    })
    .click();
  await target
    .getByRole("radio", { name: label("desktop.ledger.columns.preset.iva") })
    .click();
  await target.keyboard.press("Escape");
  const cue = grid(target).locator("[data-slot=data-grid-more-columns]");
  await expect(cue).toBeVisible();
  const scroller = grid(target);
  const before = await scroller.evaluate((element) => element.scrollLeft);
  await cue.click();
  await expect
    .poll(() => scroller.evaluate((element) => element.scrollLeft))
    .toBeGreaterThan(before);
});

test("every row says its stored status to a screen reader with each cell", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, 2026, "4T");
  await pill(target, "to_classify").click();
  const cell = dataRows(target).first().locator("[data-column=description]");
  const described = await cell.getAttribute("aria-describedby");
  expect(described).toBeTruthy();
  const said = await target.evaluate(
    (ids) =>
      ids
        .split(" ")
        .map((id) => document.getElementById(id)?.textContent ?? "")
        .join(" "),
    described!,
  );
  expect(said).toContain(label("desktop.ledger.status.pending"));
  // The status cell says its word even where only the glyph shows.
  await expect(
    dataRows(target).first().locator("[data-column=status]"),
  ).toContainText(label("desktop.ledger.status.pending"));
});

test("five thousand movements of one period are read, drawn and scrolled", async ({
  page: target,
}) => {
  test.setTimeout(120_000);
  await openLedger(target, "&ledger=large");
  await choosePeriod(target, 2026, "4T");
  await expect
    .poll(async () => (await shownOf(target)).total, { timeout: 60_000 })
    .toBeGreaterThan(5_000);
  const total = (await shownOf(target)).total;
  await expect(grid(target)).toHaveAttribute(
    "aria-rowcount",
    String(total + 1),
  );
  expect(await dataRows(target).count()).toBeLessThan(80);
  // A sort and a grouping over the whole window answer within a frame or
  // two of a person's patience.
  const started = Date.now();
  await grid(target)
    .getByRole("columnheader", { name: label("desktop.ledger.column.amount") })
    .click();
  await expect(
    grid(target).getByRole("columnheader", {
      name: label("desktop.ledger.column.amount"),
    }),
  ).toHaveAttribute("aria-sort", "ascending");
  expect(Date.now() - started).toBeLessThan(2_000);
  const scroller = grid(target);
  await scroller.evaluate((element) => {
    element.scrollTop = element.scrollHeight / 2;
  });
  await expect(dataRows(target).first()).toBeVisible();
  expect(await dataRows(target).count()).toBeLessThan(80);
});
