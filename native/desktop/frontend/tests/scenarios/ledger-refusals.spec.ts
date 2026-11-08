import { expect, test, type Locator, type Page } from "@playwright/test";
import { showLedgerColumn } from "../support/ledgerPage";
import { label } from "../support/strings";

// What the Ledger says when a staged change cannot be saved. Each refusal
// names the fact the person is missing, in the backend's own words, and leads
// to the column that fact is typed in -- including a column the preset the
// person is working in gives up for want of room. The live regions say what
// the grid holds now, never what it held before a save.

async function openLedger(target: Page, extra = "") {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off${extra}`,
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(dataRows(target).first()).toBeVisible();
}

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const tray = (target: Page) => target.locator(".ledger-tray");
const review = (target: Page) => target.locator(".ledger-review");
const editor = (target: Page) => target.locator(".ledger-cell-editor");
const search = (target: Page) =>
  page(target).getByRole("searchbox", {
    name: label("desktop.ledger.search.label"),
  });

const rowOf = (target: Page, text: string) =>
  dataRows(target).filter({
    has: target.locator("[data-column=description]", { hasText: text }),
  });
const cellOf = (row: Locator, column: string) =>
  row.locator(`[data-column=${column}]`);

async function find(target: Page, words: string) {
  await search(target).fill(words);
  await expect(dataRows(target).first()).toBeVisible();
}

async function typeInto(target: Page, cell: Locator, value: string) {
  await cell.click();
  await target.keyboard.press("Enter");
  await expect(editor(target)).toBeVisible();
  await editor(target).fill(value);
  await target.keyboard.press("Enter");
}

async function openReview(target: Page) {
  await tray(target).locator(".ledger-tray-review").click();
  await expect(review(target)).toBeVisible();
  await expect(review(target).locator(".ledger-review-summary")).not.toHaveText(
    label("desktop.ledger.apply.reading"),
  );
}

/** Switches the grid to a named column preset. */
async function usePreset(target: Page, preset: string) {
  await page(target)
    .getByRole("button", {
      name: new RegExp(`^${label("desktop.ledger.columns.title")}`),
    })
    .click();
  await target
    .locator(".ledger-columns")
    .getByRole("button", {
      name: label(`desktop.ledger.columns.preset.${preset}`),
      exact: true,
    })
    .click();
  await target.keyboard.press("Escape");
}

test("an amount typed with a sign is refused for its sign, not reported as a missing amount", async ({
  page: target,
}) => {
  await openLedger(target);
  await find(target, "bazar el faro");
  const row = rowOf(target, "BAZAR EL FARO");
  // The movement already goes out; the sign repeats what the direction says.
  await typeInto(target, cellOf(row, "amount"), "-50,00");
  // The cell keeps what was typed, marked as refused.
  await expect(cellOf(row, "amount")).toContainText("-50,00");

  await openReview(target);
  const blocker = review(target).locator("[data-blocker=amount_signed]");
  await expect(blocker).toBeVisible();
  // The sentence is the backend's: it names the magnitude and the direction.
  await expect(blocker).toContainText(
    label("application.ledger.staged_check.served.blocker.amount_signed"),
  );
  await expect(blocker).toContainText(
    label("application.ledger.staged_check.served.fix.amount_signed"),
  );
  // Nothing says the amount is a fact nobody filled in.
  await expect(
    review(target).locator("[data-blocker=draft_incomplete]"),
  ).toHaveCount(0);
  // The door leads to the two facts that disagree.
  await expect(blocker.locator(".ledger-fix-show-fields")).toBeVisible();
});

test("a new movement whose amount carries a sign is held back as a sign, with a door to it", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.locator(".ledger-add").click();
  const draft = dataRows(target).first();
  await typeInto(target, cellOf(draft, "description"), "TAXI AEROPUERTO");
  await typeInto(target, cellOf(draft, "amount"), "-50,00");

  await openReview(target);
  const blocker = review(target).locator("[data-blocker=amount_signed]");
  await expect(blocker).toBeVisible();
  await blocker.locator(".ledger-fix-go-to-draft").click();
  await expect(review(target)).toHaveCount(0);
  await expect(cellOf(dataRows(target).first(), "amount")).toContainText(
    "-50,00",
  );
});

test("the IVA preset's save refusal names the IRPF category and its door reveals the hidden column", async ({
  page: target,
}) => {
  await openLedger(target);
  await usePreset(target, "iva");
  await find(target, "estudio garcia");
  const row = rowOf(target, "ESTUDIO GARCIA").first();
  // A received invoice settled net of the IRPF withheld on it: the cash is
  // below the base plus the cuota, and only the IRPF category says why.
  await typeInto(target, cellOf(row, "taxable_base"), "2000,00");
  await typeInto(target, cellOf(row, "iva_rate"), "21");
  await typeInto(target, cellOf(row, "iva_amount"), "420,00");

  await openReview(target);
  const blocker = review(target).locator(
    "[data-blocker=needs_withholding_category]",
  );
  await expect(blocker).toBeVisible();
  // The words are the backend's, and name no Pydantic text and no field code.
  await expect(blocker).toContainText(
    label(
      "application.ledger.staged_check.served.blocker.needs_withholding_category",
    ),
  );
  await expect(blocker).not.toContainText("pydantic");
  await expect(blocker).not.toContainText("irpf_category");
  // It names the field in the product's words.
  await expect(blocker).toContainText(
    label("desktop.ledger.column.irpf_category"),
  );

  // The IVA preset gives the IRPF column up; the door brings it back and
  // puts the keyboard in it.
  await expect(
    grid(target).locator(
      "[role=columnheader][data-header-column=irpf_category]",
    ),
  ).toHaveCount(0);
  await blocker.locator(".ledger-fix-show-fields").click();
  await expect(review(target)).toHaveCount(0);
  await expect(
    grid(target).locator(
      "[role=columnheader][data-header-column=irpf_category]",
    ),
  ).toHaveCount(1);
  await expect
    .poll(async () =>
      grid(target).locator("[data-column=irpf_category]:focus").count(),
    )
    .toBe(1);
});

test("naming the IRPF category clears the refusal and the row saves", async ({
  page: target,
}) => {
  await openLedger(target);
  await usePreset(target, "everything");
  await find(target, "estudio garcia");
  const row = rowOf(target, "ESTUDIO GARCIA").first();
  await typeInto(target, cellOf(row, "taxable_base"), "2000,00");
  await typeInto(target, cellOf(row, "iva_rate"), "21");
  await typeInto(target, cellOf(row, "iva_amount"), "420,00");
  await typeInto(
    target,
    cellOf(row, "irpf_category"),
    label("desktop.ledger.irpf_category.actividad_economica"),
  );

  await openReview(target);
  await expect(
    review(target).locator("[data-blocker=needs_withholding_category]"),
  ).toHaveCount(0);
});

test("an IVA deduction kind is reviewed by its served word, never by its stored code", async ({
  page: target,
}) => {
  await openLedger(target);
  await usePreset(target, "everything");
  await showLedgerColumn(target, "classification");
  await find(target, "estudio garcia");
  const row = rowOf(target, "ESTUDIO GARCIA").first();
  await typeInto(
    target,
    cellOf(row, "iva_category"),
    label("desktop.ledger.iva_category.domestic_general"),
  );

  await openReview(target);
  const summary = review(target).locator(".ledger-summary");
  await expect(summary).toContainText(
    label("desktop.ledger.iva_category.domestic_general"),
  );
  // The stored code never reaches the person.
  await expect(summary).not.toContainText("domestic_general");
  await expect(summary).not.toContainText("domestic_current");
});

test("the live region says what the grid holds now, not what it held before the save", async ({
  page: target,
}) => {
  await openLedger(target);
  await usePreset(target, "iva");
  await find(target, "estudio garcia");
  const row = rowOf(target, "ESTUDIO GARCIA").first();
  await typeInto(target, cellOf(row, "taxable_base"), "1000,00");
  // A keyboard move over the staged cell says it is unsaved.
  await cellOf(row, "taxable_base").click();
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("ArrowUp");
  const spoken = grid(target).locator("[aria-live=polite]");
  await expect(spoken).toContainText(label("desktop.ledger.edit.row_unsaved"));

  await openReview(target);
  await review(target).locator(".ledger-apply-save").click();
  await expect(review(target).locator(".ledger-apply-done")).toBeVisible({
    timeout: 20_000,
  });
  await review(target).locator(".ledger-apply-done").click();

  // The stage is gone, so the sentence about it is gone too.
  await expect(tray(target)).toHaveCount(0);
  await expect(spoken).toHaveText("");
});
