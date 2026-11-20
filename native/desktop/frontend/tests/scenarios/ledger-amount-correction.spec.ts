import { expect, test, type Locator, type Page } from "@playwright/test";
import { grossMismatchWords } from "../../src/dev/ledgerEntryFixture";
import { captureUnrecordedQuestions } from "../support/stagedCheckCapture";
import { label } from "../support/strings";

// Correcting a movement's amount when it carries a base and an IVA amount.
// The ledger holds that the base, the IVA amount and any surcharge add up to
// the amount, so an amount moved alone is refused when it is saved. The
// review says why, in the words the ledger served, and keeps the change
// staged; the same correction with a base that moves with it saves.

async function openLedger(target: Page) {
  await captureUnrecordedQuestions(target);
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
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
const cellOf = (row: Locator, column: string) =>
  row.locator(`[data-column=${column}]`);
const headline = (target: Page) =>
  review(target).locator(".ledger-apply-headline");
const titled = (kind: string, count: number) =>
  `${label(`desktop.ledger.apply.tally.${kind}`)} · ${count}`;

async function typeInto(target: Page, cell: Locator, value: string) {
  await cell.click();
  await target.keyboard.press("Enter");
  await expect(editor(target)).toBeVisible();
  await editor(target).fill(value);
  await target.keyboard.press("Enter");
}

async function usePreset(target: Page, preset: string) {
  await page(target)
    .getByRole("button", {
      name: new RegExp(`^${label("desktop.ledger.columns.title")}`),
    })
    .click();
  await target
    .locator(".ledger-columns")
    .getByRole("radio", {
      name: label(`desktop.ledger.columns.preset.${preset}`),
      exact: true,
    })
    .click();
  await target.keyboard.press("Escape");
}

async function openReview(target: Page) {
  await tray(target).locator(".ledger-tray-review").click();
  await expect(review(target)).toBeVisible();
  await expect(review(target).locator(".ledger-review-summary")).not.toHaveText(
    label("desktop.ledger.apply.reading"),
  );
}

async function save(target: Page) {
  await review(target).locator(".ledger-apply-save").click();
  await expect(review(target).locator(".ledger-apply-done")).toBeVisible({
    timeout: 20_000,
  });
}

/** A figure as a cell draws it, in cents. */
const centsOf = (shown: string | null) =>
  Math.round(Number((shown ?? "").replace(/[^0-9.-]/g, "")) * 100);
const plain = (amountCents: number) => (amountCents / 100).toFixed(2);

/** A stored movement of the period that carries a base and an IVA amount
 * adding up to its amount, with what it holds now. */
async function purchase(target: Page) {
  await openLedger(target);
  await usePreset(target, "everything");
  const withFigures = dataRows(target).filter({
    has: target.locator("[data-column=taxable_base]", { hasText: /\d/ }),
  });
  await expect(withFigures.first()).toBeVisible();
  for (let at = 0; at < (await withFigures.count()); at += 1) {
    const row = withFigures.nth(at);
    const stored = {
      amount: centsOf(await cellOf(row, "amount").textContent()),
      base: centsOf(await cellOf(row, "taxable_base").textContent()),
      iva: centsOf(await cellOf(row, "iva_amount").textContent()),
    };
    // A reverse-charge purchase carries a base that is its whole amount.
    if (stored.iva > 0 && stored.base + stored.iva === stored.amount)
      return { row, stored };
  }
  throw new Error("The scenario ledger holds no movement with a split.");
}

test("an amount moved alone is refused with the ledger's own sentence and stays staged", async ({
  page: target,
}) => {
  const { row, stored } = await purchase(target);
  const corrected = stored.amount + 5000;
  await typeInto(target, cellOf(row, "amount"), plain(corrected));

  await openReview(target);
  await save(target);

  const sentence = grossMismatchWords(
    plain(stored.base + stored.iva),
    plain(corrected),
  );
  await expect(headline(target)).toHaveText(titled("refused", 1));
  const refused = review(target).locator("[data-outcome=refused]");
  await expect(refused).toHaveCount(1);
  // The reason is the served sentence, with the two figures that disagree,
  // not the generic "not accepted" line and not the refusal's code.
  await expect(refused).toContainText(sentence);
  await expect(refused).not.toContainText(
    label("desktop.ledger.apply.refusal.other"),
  );
  await expect(review(target)).not.toContainText(
    "REFUSED_CLI_VALIDATION_BOUNDARY",
  );

  // The change is still staged for another try.
  await review(target).locator(".ledger-apply-done").click();
  await expect(tray(target)).toBeVisible();
  await expect(cellOf(row, "amount").locator("[data-staged]")).toContainText(
    plain(corrected),
  );
});

test("an amount moved with a base that agrees saves", async ({
  page: target,
}) => {
  const { row, stored } = await purchase(target);
  const corrected = stored.amount + 5000;
  await typeInto(target, cellOf(row, "amount"), plain(corrected));
  await typeInto(
    target,
    cellOf(row, "taxable_base"),
    plain(stored.base + 5000),
  );

  await openReview(target);
  await save(target);

  await expect(headline(target)).toHaveText(titled("applied", 1));
  await expect(review(target).locator("[data-outcome]")).toHaveCount(0);
  await review(target).locator(".ledger-apply-done").click();
  await expect(tray(target)).toHaveCount(0);
  const saved = dataRows(target)
    .filter({
      has: target.locator("[data-column=amount]", {
        hasText: new RegExp(plain(corrected).replace(".", "\\.")),
      }),
    })
    .first();
  await expect(cellOf(saved, "taxable_base")).toContainText(
    plain(stored.base + 5000),
  );
  await expect(cellOf(saved, "iva_amount")).toContainText(plain(stored.iva));
});
