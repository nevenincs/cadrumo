import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { showLedgerColumn } from "../support/ledgerPage";
import { label } from "../support/strings";

// Staged editing on the Ledger page over the scenario's ledger: cell
// editors in the product's grammar, paste, fill, undo and revert, new
// movements, the page-wide tray, the leave guard, and the review and apply
// with each outcome the product can give. Nothing is saved until the review
// says so, and the grid keeps drawing what is stored.

const engine = readFileSync(
  fileURLToPath(
    new URL("../../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);

async function open(target: Page, extra = "", scheme?: "light" | "dark") {
  if (scheme)
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off${extra}`,
  );
}

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const tray = (target: Page) => target.locator(".ledger-tray");
const review = (target: Page) => target.locator(".ledger-review");
const editor = (target: Page) => target.locator(".ledger-cell-editor");
const toast = (target: Page) => page(target).locator(".ledger-toast");
const search = (target: Page) =>
  page(target).getByRole("searchbox", {
    name: label("desktop.ledger.search.label"),
  });

async function openLedger(target: Page, extra = "", scheme?: "light" | "dark") {
  await open(target, extra, scheme);
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(dataRows(target).first()).toBeVisible();
}

/** The row whose description is `text`, among those drawn. */
const rowOf = (target: Page, text: string) =>
  dataRows(target).filter({
    has: target.locator("[data-column=description]", { hasText: text }),
  });
const cellOf = (row: Locator, column: string) =>
  row.locator(`[data-column=${column}]`);

/** Narrows the grid to the movements whose text holds `words`. */
async function find(target: Page, words: string) {
  await search(target).fill(words);
  await expect(dataRows(target).first()).toBeVisible();
}

/** Types `value` into a cell's editor and commits it with Enter. */
async function typeInto(target: Page, cell: Locator, value: string) {
  await cell.click();
  await target.keyboard.press("Enter");
  await expect(editor(target)).toBeVisible();
  await editor(target).fill(value);
  await target.keyboard.press("Enter");
}

/** Chooses `option` in a choice cell's list. */
async function chooseIn(target: Page, cell: Locator, option: string) {
  await cell.click();
  await target.keyboard.press("Enter");
  const list = target.locator(".ledger-cell-choice");
  await expect(list).toBeVisible();
  await target.keyboard.type(option);
  await list.getByRole("option", { name: option, exact: true }).click();
  await expect(list).toHaveCount(0);
}

const trayCount = async (target: Page) =>
  Number(
    await tray(target)
      .locator(".ledger-tray-toggle span[aria-hidden=true]")
      .textContent(),
  );

async function openReview(target: Page) {
  await tray(target).locator(".ledger-tray-review").click();
  await expect(review(target)).toBeVisible();
  await expect(review(target).locator(".ledger-review-summary")).not.toHaveText(
    label("desktop.ledger.apply.reading"),
  );
}

/** The result's title: its worst outcome and how many it holds. */
const headline = (target: Page) =>
  review(target).locator(".ledger-apply-headline");
const titled = (kind: string, count: number) =>
  `${label(`desktop.ledger.apply.tally.${kind}`)} · ${count}`;

/** The grid's active cell holds the focus. */
async function focusOnGrid(target: Page) {
  await expect
    .poll(() =>
      target.evaluate(
        () =>
          document.activeElement?.closest(".ledger-page [role=grid]") !== null,
      ),
    )
    .toBe(true);
}

async function save(target: Page) {
  await review(target).locator(".ledger-apply-save").click();
  await expect(review(target).locator(".ledger-apply-done")).toBeVisible({
    timeout: 20_000,
  });
}

test("an edit is staged beside the stored value, and the strip and counts stay stored", async ({
  page: target,
}) => {
  await openLedger(target);
  const strip = page(target).locator(".ledger-readiness");
  const counts = () =>
    strip.locator("[data-readiness] span[aria-hidden=true]").allTextContents();
  const before = await counts();
  const row = dataRows(target).first();
  const description = await cellOf(row, "description").textContent();
  await typeInto(target, cellOf(row, "counterparty"), "Gráficas Turia SL");
  const cell = cellOf(rowOf(target, description!), "counterparty");
  await expect(cell.locator("[data-staged]")).toContainText(
    "Gráficas Turia SL",
  );
  // In words for a screen reader, beside the unsaved edge of the row.
  await expect(cell).toContainText(
    label("desktop.ledger.edit.changed_was", { was: "" }).trim(),
  );
  await expect(
    rowOf(target, description!).locator("[data-unsaved]"),
  ).toHaveCount(1);
  // The pills count what is stored, and say that the edit is not in them.
  expect(await counts()).toEqual(before);
  await expect(strip).toContainText(
    label("desktop.ledger.readiness.unsaved", { count: 1 }),
  );
  // One movement changed: the tray counts it once, in the page's unit.
  await expect(tray(target)).toBeVisible();
  expect(await trayCount(target)).toBe(1);
});

test("the review opens on the chord the tray shows, from either Enter key, and not with Shift", async ({
  page: target,
}) => {
  await openLedger(target);
  const row = dataRows(target).first();
  await typeInto(target, cellOf(row, "counterparty"), "Gráficas Turia SL");
  await expect(tray(target)).toBeVisible();
  await expect(tray(target).locator(".ledger-tray-review")).toHaveAttribute(
    "aria-keyshortcuts",
    "Control+Enter",
  );
  await cellOf(row, "description").click();
  await target.keyboard.press("Control+Shift+Enter");
  await target.keyboard.press("Alt+Enter");
  await expect(review(target)).toHaveCount(0);
  await target.keyboard.press("Control+Enter");
  await expect(review(target)).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(review(target)).toHaveCount(0);
  await cellOf(row, "description").click();
  await target.keyboard.press("Control+NumpadEnter");
  await expect(review(target)).toBeVisible();
});

test("the amount editor refuses what could be read two ways, echoing it, and saves the shortest form", async ({
  page: target,
}) => {
  await openLedger(target);
  await find(target, "softnube");
  const row = rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION");
  await cellOf(row, "amount").click();
  await target.keyboard.press("Enter");
  // In English this is a thousand and more, or one and a bit.
  await editor(target).fill("1,234");
  await target.keyboard.press("Enter");
  // Refused in words that echo the raw value; the editor stays open.
  await expect(editor(target)).toHaveAttribute("aria-invalid", "true");
  await expect(target.locator(".ledger-cell-note")).toContainText(
    label("desktop.ledger.edit.refusal.ambiguous_grouping", {
      raw: "1,234",
      suggestion: "",
      limit: "",
    }),
  );
  await editor(target).fill("40.50");
  await target.keyboard.press("Enter");
  await expect(editor(target)).toHaveCount(0);
  await expect(cellOf(row, "amount").locator("[data-staged]")).toContainText(
    "40.50",
  );
  // An amount gives the movement a new reference, said with its own mark.
  await expect(cellOf(row, "amount")).toContainText(
    label("desktop.ledger.edit.new_identity"),
  );
  await openReview(target);
  await save(target);
  // The product's single update refuses any but the shortest spelling.
  // Everything saved: the result says so once and lists nothing.
  await expect(headline(target)).toHaveText(titled("applied", 1));
  await expect(review(target).locator("[data-outcome]")).toHaveCount(0);
  await review(target).locator(".ledger-apply-done").click();
  await focusOnGrid(target);
  await expect(rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION")).toHaveCount(1);
  await expect(
    cellOf(rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION"), "amount"),
  ).toHaveText(/40\.50/);
  await expect(tray(target)).toHaveCount(0);
});

test("a share is a percentage in one grammar: 21 is 21%, 0.21 is 0.21%", async ({
  page: target,
}) => {
  await openLedger(target);
  await find(target, "comision mantenimiento");
  // The IVA preset shows the rate column.
  await page(target)
    .getByRole("button", {
      name: new RegExp(`^${label("desktop.ledger.columns.title")}`),
    })
    .click();
  await target
    .locator(".ledger-columns")
    .getByRole("radio", { name: label("desktop.ledger.columns.preset.iva") })
    .click();
  await target.keyboard.press("Escape");
  const row = rowOf(target, "COMISION MANTENIMIENTO CUENTA");
  await cellOf(row, "iva_rate").click();
  await target.keyboard.press("Enter");
  await editor(target).fill("0.21");
  await target.keyboard.press("Enter");
  await expect(cellOf(row, "iva_rate").locator("[data-staged]")).toContainText(
    "0.21%",
  );
  await cellOf(row, "iva_rate").click();
  await target.keyboard.press("Enter");
  await editor(target).fill("21");
  await target.keyboard.press("Enter");
  await expect(cellOf(row, "iva_rate").locator("[data-staged]")).toContainText(
    "21%",
  );
});

test("Delete clears an optional cell, and a required one says it cannot be cleared", async ({
  page: target,
}) => {
  await openLedger(target);
  await find(target, "comision mantenimiento");
  const row = rowOf(target, "COMISION MANTENIMIENTO CUENTA");
  await cellOf(row, "category").click();
  await target.keyboard.press("Delete");
  await expect(cellOf(row, "category").locator("[data-staged]")).toContainText(
    label("desktop.ledger.edit.cleared"),
  );
  await cellOf(row, "amount").click();
  await target.keyboard.press("Delete");
  const amount = cellOf(row, "amount");
  await expect(amount.locator("[data-refused]")).toHaveCount(1);
  await expect(amount).toHaveAttribute("aria-invalid", "true");
  // The clear goes through a single classification, never the bulk.
  await openReview(target);
  await save(target);
  const submitted = await target.evaluate(
    () => window.__scenarioHostCalls ?? [],
  );
  expect(submitted).toContain("ledger ledger.classify.single");
  expect(submitted).not.toContain("ledger ledger.classify.bulk");
});

/** The scenario ledger's controls for what no person does here. */
const ledgerControls = {
  nextWrites: (target: Page, outcomes: ("unknown" | "refused")[]) =>
    target.evaluate(
      (next) => window.__scenarioLedger!.nextWrites(next),
      outcomes,
    ),
  editElsewhere: (
    target: Page,
    id: string,
    field: string,
    value: string | null,
  ) =>
    target.evaluate(
      ([key, name, set]) =>
        window.__scenarioLedger!.editElsewhere(key!, name!, set ?? null),
      [id, field, value] as const,
    ),
};
const keyOf = async (row: Locator) => (await row.getAttribute("data-key"))!;

/** Puts `text` on the grid's paste, as a spreadsheet's copy would. */
const paste = (target: Page, text: string) =>
  grid(target).evaluate((element, clip) => {
    const data = new DataTransfer();
    data.setData("text/plain", clip);
    element.dispatchEvent(
      new ClipboardEvent("paste", { clipboardData: data, bubbles: true }),
    );
  }, text);

test("classifying is one command: hidden selections are held, Business asks a category, Mixed a share", async ({
  page: target,
}) => {
  await openLedger(target);
  const first = rowOf(target, "PAPELERIA TRAZO");
  const second = rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION");
  await first.locator("input[type=checkbox]").click();
  await second.locator("input[type=checkbox]").click();
  await find(target, "papeleria");
  await cellOf(first, "description").click({ modifiers: ["Control"] });
  await cellOf(first, "description").click({ modifiers: ["Control"] });
  await target.keyboard.press("Alt+KeyB");
  // A selection the person cannot see is never classified unseen.
  await expect(target.locator(".ledger-classify")).toHaveCount(0);
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.selection.hidden", { hidden: 1, selected: 2 }),
  );
  await page(target)
    .getByRole("button", {
      name: label("desktop.ledger.selection.keep_visible"),
    })
    .click();
  await cellOf(first, "description").click();
  await target.keyboard.press("Alt+KeyB");
  const dialog = target.locator(".ledger-classify");
  await expect(dialog).toBeVisible();
  await dialog.locator(".ledger-classify-category").click();
  await target
    .getByRole("option", {
      name: label("desktop.ledger.category.material_oficina"),
    })
    .click();
  await dialog.locator(".ledger-classify-stage").click();
  await expect(toast(target)).toContainText(
    label("desktop.ledger.category.material_oficina"),
  );
  await expect(
    cellOf(first, "classification").locator("[data-staged]"),
  ).toContainText(label("desktop.ledger.classification.business"));
  // The stored status still reads as stored: nothing says reviewed.
  await expect(cellOf(first, "status")).toContainText(
    label("desktop.ledger.status.pending"),
  );
  // Mixed asks for a share and a category a share applies to, and
  // refuses a fraction.
  await cellOf(first, "description").click();
  await target.keyboard.press("Alt+KeyM");
  await expect(dialog).toBeVisible();
  await dialog.locator(".ledger-classify-category").click();
  await expect(
    target.getByRole("option", {
      name: label("desktop.ledger.category.material_oficina"),
    }),
  ).toHaveCount(0);
  await target
    .getByRole("option", {
      name: label("desktop.ledger.category.telefonia_fija"),
    })
    .click();
  await dialog.getByLabel(label("desktop.ledger.classify.share")).fill("101");
  await dialog.locator(".ledger-classify-stage").click();
  await expect(dialog).toContainText(
    label("desktop.ledger.classify.share_refused", { raw: "101" }),
  );
  await dialog.getByLabel(label("desktop.ledger.classify.share")).fill("40");
  await dialog.locator(".ledger-classify-stage").click();
  await expect(
    cellOf(first, "classification").locator("[data-staged]"),
  ).toContainText("40%");
});

test("the review flags an expense category on income, which no expense reads", async ({
  page: target,
}) => {
  await openLedger(target);
  // A stored Business income, given a spending category in its cell.
  const income = rowOf(target, "TRANSFERENCIA TALLERES ONDARA");
  await chooseIn(
    target,
    cellOf(income, "category"),
    label("desktop.ledger.category.vehiculo_combustible"),
  );
  // The same category on an expense is no mismatch.
  await chooseIn(
    target,
    cellOf(rowOf(target, "COMISION MANTENIMIENTO CUENTA"), "category"),
    label("desktop.ledger.category.vehiculo_combustible"),
  );
  await openReview(target);
  const chip = review(target).locator("[data-mismatch=income_category]");
  await expect(chip).toHaveText(
    label("desktop.ledger.apply.mismatch.income_category", { count: 1 }),
  );
});

test("a transfer takes no tax field and only Personal", async ({
  page: target,
}) => {
  await openLedger(target);
  await find(target, "traspaso");
  const row = dataRows(target).first();
  await cellOf(row, "category").click();
  await target.keyboard.press("Enter");
  await expect(target.locator(".ledger-cell-choice")).toHaveCount(0);
  await expect(cellOf(row, "category")).toHaveAttribute(
    "aria-readonly",
    "true",
  );
  await target.keyboard.press("Alt+KeyB");
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.classify.transfers_only"),
  );
});

test("a paste of several rows is previewed, blanks change nothing, and an open quote is refused", async ({
  page: target,
}) => {
  await openLedger(target);
  await showLedgerColumn(target, "group_label");
  await find(target, "farmacia nube");
  const rows = dataRows(target);
  await cellOf(rows.first(), "counterparty").click();
  await paste(target, "Farmacia Uno\nFarmacia Dos\n\nFarmacia Cuatro");
  const preview = target.locator(".ledger-paste");
  await expect(preview).toBeVisible();
  await expect(preview).toContainText(
    label("desktop.ledger.paste.description", { rows: 4 }),
  );
  await expect(preview).toContainText(label("desktop.ledger.paste.blanks"));
  // Nothing is staged until Paste.
  await expect(tray(target)).toHaveCount(0);
  await preview.locator(".ledger-paste-apply").click();
  await expect(preview).toHaveCount(0);
  await expect(
    cellOf(rows.nth(0), "counterparty").locator("[data-staged]"),
  ).toContainText("Farmacia Uno");
  await expect(
    cellOf(rows.nth(2), "counterparty").locator("[data-staged]"),
  ).toHaveCount(0);
  expect(await trayCount(target)).toBe(3);
  // A quote left open is refused whole rather than guessed.
  await cellOf(rows.nth(0), "group_label").click();
  await paste(target, '"una nota\tsin cerrar');
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.paste.refused_unclosed_quote"),
  );
  expect(await trayCount(target)).toBe(3);
});

test("a paste that changes nothing names its column and first refusal, and offers only Cancel", async ({
  page: target,
}) => {
  await openLedger(target);
  await find(target, "farmacia nube");
  const rows = dataRows(target);
  await cellOf(rows.first(), "amount").click();
  await paste(target, "Proyecto A\nProyecto B\nProyecto C");
  const preview = target.locator(".ledger-paste");
  await expect(preview.getByRole("heading")).toHaveText(
    label("desktop.ledger.paste.title_into", {
      columns: label("desktop.ledger.column.amount"),
    }),
  );
  await expect(preview.locator(".ledger-paste-refusal")).toContainText(
    `${label("desktop.ledger.column.amount")}: `,
  );
  await expect(preview.locator(".ledger-paste-refusal")).toContainText(
    "Proyecto A",
  );
  await expect(preview.locator(".ledger-paste-apply")).toHaveAttribute(
    "aria-disabled",
    "true",
  );
  await expect(
    preview.locator("[data-slot=dialog-footer]").getByRole("button", {
      name: label("desktop.ledger.paste.cancel"),
      exact: true,
    }),
  ).toBeFocused();
  await target.keyboard.press("Escape");
  await expect(preview).toHaveCount(0);
  // Closing hands the focus back to the cell the paste went to.
  await expect(cellOf(rows.first(), "amount")).toBeFocused();
  await expect(tray(target)).toHaveCount(0);
});

test("fill down copies the top value, undo and redo step through it, and revert takes one cell back", async ({
  page: target,
}) => {
  await openLedger(target);
  await showLedgerColumn(target, "group_label");
  await find(target, "farmacia nube");
  const rows = dataRows(target);
  await typeInto(target, cellOf(rows.nth(0), "group_label"), "Ticket guardado");
  await cellOf(rows.nth(0), "group_label").click();
  await target.keyboard.press("Shift+ArrowDown");
  await target.keyboard.press("Shift+ArrowDown");
  await target.keyboard.press("Control+KeyD");
  for (const at of [1, 2])
    await expect(
      cellOf(rows.nth(at), "group_label").locator("[data-staged]"),
    ).toContainText("Ticket guardado");
  await target.keyboard.press("Control+KeyZ");
  await expect(
    cellOf(rows.nth(1), "group_label").locator("[data-staged]"),
  ).toHaveCount(0);
  await expect(
    cellOf(rows.nth(0), "group_label").locator("[data-staged]"),
  ).toHaveCount(1);
  await target.keyboard.press("Control+Shift+KeyZ");
  await expect(
    cellOf(rows.nth(2), "group_label").locator("[data-staged]"),
  ).toHaveCount(1);
  // Ctrl+Alt+Z takes back only the active cell, and types no z.
  await cellOf(rows.nth(1), "group_label").click();
  await target.keyboard.press("Control+Alt+KeyZ");
  await expect(editor(target)).toHaveCount(0);
  await expect(
    cellOf(rows.nth(1), "group_label").locator("[data-staged]"),
  ).toHaveCount(0);
  await expect(
    cellOf(rows.nth(2), "group_label").locator("[data-staged]"),
  ).toHaveCount(1);
  // Revert movement from the row's menu, which shows the chords of the keys
  // pressed above: revert cell and fill down. Reverting a whole movement has
  // no key, so none is shown.
  await cellOf(rows.nth(2), "group_label").click({ button: "right" });
  const menu = target.getByRole("menu");
  const shown = (key: string) =>
    menu
      .getByRole("menuitem", { name: label(key), exact: true })
      .locator("kbd");
  const mac = process.platform === "darwin";
  await expect(shown("desktop.ledger.edit.revert_cell")).toHaveText(
    mac ? ["⌃", "⌥", "Z"] : ["Ctrl", "Alt", "Z"],
  );
  await expect(shown("desktop.ledger.fill.down")).toHaveText(
    mac ? ["⌘", "D"] : ["Ctrl", "D"],
  );
  await expect(shown("desktop.ledger.edit.revert_movement")).toHaveCount(0);
  await target
    .getByRole("menuitem", {
      name: label("desktop.ledger.edit.revert_movement"),
    })
    .click();
  await expect(
    cellOf(rows.nth(2), "group_label").locator("[data-staged]"),
  ).toHaveCount(0);
});

test("a change that adds many saves one at a time says what it costs first", async ({
  page: target,
}) => {
  await openLedger(target);
  const rows = dataRows(target);
  await typeInto(
    target,
    cellOf(rows.nth(0), "counterparty"),
    "Proveedor común",
  );
  await cellOf(rows.nth(0), "counterparty").click();
  for (let step = 0; step < 14; step += 1)
    await target.keyboard.press("Shift+ArrowDown");
  await target.keyboard.press("Control+KeyD");
  const cost = target.locator(".ledger-cost");
  await expect(cost).toBeVisible();
  expect(await trayCount(target)).toBe(1);
  await cost.locator(".ledger-cost-stage").click();
  await expect.poll(() => trayCount(target)).toBeGreaterThan(10);
});

/** Fills in the new movement at the top of the grid, field by field. */
async function fillDraft(target: Page, description: string) {
  const draft = dataRows(target).first();
  await expect(draft.locator(".ledger-draft-status")).toBeVisible();
  // Nothing is assumed: no date, direction or amount.
  await expect(cellOf(draft, "date")).toContainText(
    label("desktop.ledger.draft.required"),
  );
  await expect(cellOf(draft, "direction")).toContainText(
    label("desktop.ledger.draft.required"),
  );
  // It opens on its date.
  await expect(cellOf(draft, "date")).toBeFocused();
  await target.keyboard.type("2026-10-21");
  await target.keyboard.press("Enter");
  await typeInto(target, cellOf(draft, "description"), description);
  await typeInto(target, cellOf(draft, "amount"), "12.40");
  await chooseIn(
    target,
    cellOf(draft, "direction"),
    label("desktop.ledger.direction.outgoing"),
  );
  return draft;
}

test("a new movement starts empty, is staged like an edit, and its add is the same add after an unknown outcome", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.locator(".ledger-add").click();
  await fillDraft(target, "TAXI AEROPUERTO");
  expect(await trayCount(target)).toBe(1);
  // The currency is asked for too, in the review.
  await openReview(target);
  const blocker = review(target).locator("[data-blocker=draft_incomplete]");
  await expect(blocker).toBeVisible();
  await blocker.getByLabel(label("desktop.ledger.field.currency")).fill("EUR");
  await blocker
    .getByRole("button", {
      name: label("desktop.ledger.apply.fix.set_currency"),
    })
    .click();
  await expect(blocker).toHaveCount(0);
  await ledgerControls.nextWrites(target, ["unknown"]);
  await save(target);
  await expect(review(target).locator(".ledger-apply-unknown")).toBeVisible();
  await review(target).locator(".ledger-apply-done").click();
  // Writes pause, said once on the page, until the ledger is read again.
  const paused = page(target).locator(".ledger-paused");
  await expect(paused).toBeVisible();
  await expect(tray(target).locator(".ledger-tray-review")).toHaveAttribute(
    "aria-disabled",
    "true",
  );
  await paused.locator(".ledger-paused-reread").click();
  // An add is never told by a read: the draft stays, with its key.
  await expect(page(target).locator(".ledger-findings")).toBeVisible();
  expect(await trayCount(target)).toBe(1);
  await openReview(target);
  await save(target);
  await expect(review(target).locator("[data-outcome=unchanged]")).toHaveCount(
    1,
  );
  await review(target).locator(".ledger-apply-done").click();
  await find(target, "taxi aeropuerto");
  // Sent twice under one key, the movement exists once.
  await expect(rowOf(target, "TAXI AEROPUERTO")).toHaveCount(1);
  await expect(tray(target)).toHaveCount(0);
});

test("leaving with staged work asks first, from a shell chord too", async ({
  page: target,
}) => {
  await openLedger(target);
  await showLedgerColumn(target, "group_label");
  await typeInto(
    target,
    cellOf(rowOf(target, "PAPELERIA TRAZO"), "group_label"),
    "Oficina",
  );
  await target.keyboard.press("Control+Shift+KeyD");
  const leave = target.locator(".ledger-leave");
  await expect(leave).toBeVisible();
  await leave
    .getByRole("button", { name: label("desktop.ledger.leave.cancel") })
    .first()
    .click();
  await expect(leave).toHaveCount(0);
  await expect(page(target)).toBeVisible();
  expect(await trayCount(target)).toBe(1);
  // Signing out asks the same.
  await target.keyboard.press("Control+Shift+KeyD");
  await leave.locator(".ledger-leave-discard").click();
  await expect(page(target)).toHaveCount(0);
});

test("an unknown write pauses every later write until a re-read says whether it saved", async ({
  page: target,
}) => {
  await openLedger(target);
  await showLedgerColumn(target, "group_label");
  const row = rowOf(target, "PAPELERIA TRAZO");
  await typeInto(target, cellOf(row, "counterparty"), "Trazo Papelería SL");
  await typeInto(
    target,
    cellOf(rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION"), "group_label"),
    "Software",
  );
  await openReview(target);
  await ledgerControls.nextWrites(target, ["unknown"]);
  await save(target);
  await expect(review(target).locator("[data-outcome=unknown]")).toHaveCount(1);
  // Titled by the worst outcome, never as nothing saved.
  await expect(headline(target)).toHaveText(titled("unknown", 1));
  // The write after it was not sent.
  await expect(review(target).locator("[data-outcome=not_sent]")).toHaveCount(
    1,
  );
  await review(target).locator(".ledger-apply-reread").click();
  await expect(page(target).locator(".ledger-findings")).toContainText(
    label("desktop.ledger.paused.found_saved", {
      movement: "PAPELERIA TRAZO",
    }),
  );
  await review(target).locator(".ledger-apply-done").click();
  await expect(page(target).locator(".ledger-paused [role=alert]")).toHaveCount(
    0,
  );
  // What saved left the stage; what was not sent is still staged.
  await expect(
    cellOf(rowOf(target, "PAPELERIA TRAZO"), "counterparty"),
  ).toHaveText("Trazo Papelería SL");
  expect(await trayCount(target)).toBe(1);
});

test("a write the read after it shows saved leaves the stage, and the re-read says it was saved", async ({
  page: target,
}) => {
  await openLedger(target);
  await showLedgerColumn(target, "group_label");
  await typeInto(
    target,
    cellOf(rowOf(target, "PAPELERIA TRAZO"), "counterparty"),
    "Trazo Papelería SL",
  );
  await typeInto(
    target,
    cellOf(rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION"), "group_label"),
    "Software",
  );
  await openReview(target);
  await ledgerControls.nextWrites(target, ["unknown"]);
  await save(target);
  await review(target).locator(".ledger-apply-done").click();
  await focusOnGrid(target);
  // The scenario landed the write: no staged value stands equal to the
  // stored one, while writes stay paused until the person re-reads.
  const counterparty = cellOf(rowOf(target, "PAPELERIA TRAZO"), "counterparty");
  await expect(counterparty).toHaveText("Trazo Papelería SL");
  await expect(counterparty.locator("[data-staged]")).toHaveCount(0);
  expect(await trayCount(target)).toBe(1);
  const paused = page(target).locator(".ledger-paused");
  await expect(paused).toContainText(label("desktop.ledger.paused.title"));
  await paused.locator(".ledger-paused-reread").click();
  await expect(page(target).locator(".ledger-findings")).toContainText(
    label("desktop.ledger.paused.found_saved", {
      movement: "PAPELERIA TRAZO",
    }),
  );
  // The note stays until it is dismissed.
  await expect(page(target).locator(".ledger-paused [role=alert]")).toHaveCount(
    0,
  );
  expect(await trayCount(target)).toBe(1);
});

test("the review leads with its summary and folds the list of movements", async ({
  page: target,
}) => {
  await openLedger(target);
  await typeInto(
    target,
    cellOf(rowOf(target, "PAPELERIA TRAZO"), "counterparty"),
    "Trazo SL",
  );
  await typeInto(
    target,
    cellOf(rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION"), "counterparty"),
    "SoftNube Ltd",
  );
  await openReview(target);
  const list = review(target).locator(".ledger-review-rows");
  await expect(list.locator(".ledger-review-rows-toggle")).toHaveText(
    `${label("desktop.ledger.apply.summary_movements")} · 2`,
  );
  await expect(list.locator("[data-entry]")).toHaveCount(0);
  // A summary row's "Show rows" opens the list on its movements.
  await review(target)
    .locator(".ledger-summary")
    .getByRole("button", { name: label("desktop.ledger.apply.show_rows") })
    .first()
    .click();
  await expect(list.locator("[data-entry]")).toHaveCount(1);
  // A minute or less of single saves says no time.
  await expect(review(target).locator(".ledger-review-summary")).toHaveText(
    label("desktop.ledger.apply.one_by_one_quick", { count: 2 }),
  );
});

test("a part refused whole saves nothing of it and keeps it staged", async ({
  page: target,
}) => {
  await openLedger(target);
  await cellOf(rowOf(target, "PAPELERIA TRAZO"), "description").click();
  await target.keyboard.press("Alt+KeyP");
  await typeInto(
    target,
    cellOf(rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION"), "counterparty"),
    "SoftNube Ltd",
  );
  await openReview(target);
  await expect(review(target).locator(".ledger-review-summary")).toContainText(
    label("desktop.ledger.apply.together", { count: 1 }),
  );
  await ledgerControls.nextWrites(target, ["refused"]);
  await save(target);
  await expect(
    review(target).locator("[data-part=part][data-outcome=refused]"),
  ).toContainText(label("desktop.ledger.apply.part_refused"));
  await expect(headline(target)).toHaveText(titled("refused", 1));
  // Only what did not save is listed; the saved one is counted.
  await expect(review(target).locator("[data-outcome=applied]")).toHaveCount(0);
  await expect(review(target).locator("[data-tally=applied]")).toContainText(
    "1",
  );
  // The refusal's code is shown nowhere, and a re-read is offered.
  await expect(review(target)).not.toContainText("precondition_failed");
  await expect(
    review(target).locator(".ledger-apply-refused-reread"),
  ).toBeVisible();
  await review(target).locator(".ledger-apply-done").click();
  // Undo steps back through what did not save; the saved edit stays saved.
  expect(await trayCount(target)).toBe(1);
  await cellOf(rowOf(target, "PAPELERIA TRAZO"), "description").click();
  await target.keyboard.press("Control+KeyZ");
  await expect(tray(target)).toHaveCount(0);
  await expect(
    cellOf(rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION"), "counterparty"),
  ).toHaveText("SoftNube Ltd");
  await target.keyboard.press("Control+KeyZ");
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.edit.undo_applied"),
  );
});

test("a movement changed elsewhere asks only where both changed the same field", async ({
  page: target,
}) => {
  await openLedger(target);
  const trazo = rowOf(target, "PAPELERIA TRAZO");
  const softnube = rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION");
  await typeInto(target, cellOf(trazo, "counterparty"), "Mía SL");
  await typeInto(target, cellOf(softnube, "counterparty"), "SoftNube Ltd");
  await ledgerControls.editElsewhere(
    target,
    await keyOf(trazo),
    "counterparty",
    "Suya SL",
  );
  // Another field changed elsewhere is no question.
  await ledgerControls.editElsewhere(
    target,
    await keyOf(softnube),
    "notes",
    "Recibo pedido",
  );
  await tray(target).locator(".ledger-tray-review").click();
  const conflicts = review(target).locator(".ledger-conflicts");
  await expect(conflicts.locator("[data-conflict]")).toHaveCount(1);
  await expect(conflicts).toContainText("Suya SL");
  await expect(conflicts).toContainText("Mía SL");
  const go = review(target).locator(".ledger-conflicts-continue");
  await expect(go).toHaveAttribute("aria-disabled", "true");
  await conflicts.locator(".ledger-conflict-theirs").click();
  await review(target).locator(".ledger-conflicts-looked").check();
  await go.click();
  // Taking theirs dropped the staged change.
  await expect(review(target).locator(".ledger-review-summary")).toContainText(
    label("desktop.ledger.apply.one_by_one_quick", { count: 1 }),
  );
  await save(target);
  await review(target).locator(".ledger-apply-done").click();
  await expect(cellOf(trazo, "counterparty")).toHaveText("Suya SL");
});

test("an unchanged row is read again and shows what is stored before its change is dropped", async ({
  page: target,
}) => {
  await openLedger(target);
  const row = rowOf(target, "PAPELERIA TRAZO");
  await cellOf(row, "description").click();
  await target.keyboard.press("Alt+KeyP");
  const id = await keyOf(row);
  await ledgerControls.editElsewhere(
    target,
    id,
    "business_classification",
    "PERSONAL",
  );
  await tray(target).locator(".ledger-tray-review").click();
  await review(target).locator(".ledger-conflict-mine").click();
  await review(target).locator(".ledger-conflicts-looked").check();
  await review(target).locator(".ledger-conflicts-continue").click();
  await save(target);
  const unchanged = review(target).locator("[data-outcome=unchanged]");
  await expect(unchanged).toHaveCount(1);
  await expect(unchanged).toContainText(
    label("desktop.ledger.apply.outcome.unchanged_value", {
      field: label("desktop.ledger.column.classification"),
      value: label("desktop.ledger.classification.personal"),
    }),
  );
  await review(target).locator(".ledger-apply-done").click();
  await expect(tray(target)).toHaveCount(0);
});

test("the tray counts movements, new movements and actions on every section", async ({
  page: target,
}) => {
  await openLedger(target);
  await showLedgerColumn(target, "group_label");
  const row = rowOf(target, "PAPELERIA TRAZO");
  await typeInto(target, cellOf(row, "counterparty"), "Trazo SL");
  await typeInto(target, cellOf(row, "group_label"), "Oficina");
  expect(await trayCount(target)).toBe(1);
  await target.locator(".ledger-add").click();
  await target.keyboard.press("Escape");
  expect(await trayCount(target)).toBe(2);
  const toggle = tray(target).locator(".ledger-tray-toggle");
  await expect(toggle).toHaveAttribute(
    "aria-label",
    label("desktop.ledger.tray.name", {
      count: 2,
      what: [
        label("desktop.ledger.tray.edits", { edits: 2, movements: 1 }),
        label("desktop.ledger.tray.new", { count: 1 }),
      ].join(" · "),
    }),
  );
  await target
    .getByRole("tab", {
      name: new RegExp(label("desktop.ledger.section.invoices")),
    })
    .click();
  await expect(tray(target)).toBeVisible();
  expect(await trayCount(target)).toBe(2);
});

test("neither the grid nor a cell editor takes a shell chord", async ({
  page: target,
}) => {
  await openLedger(target);
  const palette = target.locator(".palette");
  await cellOf(rowOf(target, "PAPELERIA TRAZO"), "counterparty").click();
  await target.keyboard.press("Control+KeyK");
  await expect(palette).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(palette).toBeHidden();
  await cellOf(rowOf(target, "PAPELERIA TRAZO"), "counterparty").click();
  await target.keyboard.press("Enter");
  await expect(editor(target)).toBeVisible();
  await target.keyboard.press("Control+KeyK");
  await expect(palette).toBeVisible();
});

async function audit(target: Page) {
  await target.evaluate(engine);
  return target.evaluate(async () => {
    const axe = (
      window as unknown as {
        axe: {
          run(
            context: unknown,
            options: unknown,
          ): Promise<{
            violations: { id: string; nodes: { target: string[] }[] }[];
          }>;
        };
      }
    ).axe;
    const result = await axe.run(
      { exclude: [[".docs-frame"], [".xterm"]] },
      { resultTypes: ["violations"] },
    );
    return result.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.map((node) => node.target.join(" ")),
    }));
  });
}

for (const scheme of ["light", "dark"] as const)
  test(`the tray and the review have no accessibility violations (${scheme})`, async ({
    page: target,
  }) => {
    await openLedger(target, "", scheme);
    await expect(target.locator("html")).toHaveAttribute("data-scheme", scheme);
    await typeInto(
      target,
      cellOf(rowOf(target, "PAPELERIA TRAZO"), "counterparty"),
      "Trazo SL",
    );
    await target.locator(".ledger-add").click();
    await target.keyboard.press("Escape");
    await tray(target).locator(".ledger-tray-toggle").click();
    expect(await audit(target)).toEqual([]);
    await openReview(target);
    expect(await audit(target)).toEqual([]);
  });
