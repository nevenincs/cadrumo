import { expect, test, type Locator, type Page } from "@playwright/test";
import { captureUnrecordedQuestions } from "../support/stagedCheckCapture";
import { label } from "../support/strings";

// Batch editing on the Ledger page over the scenario's ledger: several
// movements selected with Ctrl, one category asked for all of them from the
// selection actions, reviewed as one change, saved, and then removed from two.

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const tray = (target: Page) => target.locator(".ledger-tray");
const review = (target: Page) => target.locator(".ledger-review");
const toast = (target: Page) => page(target).locator(".ledger-toast");
const classify = (target: Page) => target.locator(".ledger-classify");

const rowOf = (target: Page, text: string) =>
  dataRows(target).filter({
    has: target.locator("[data-column=description]", { hasText: text }),
  });
const categoryOf = (row: Locator) => row.locator("[data-column=category]");

async function openLedger(target: Page) {
  await captureUnrecordedQuestions(target);
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(dataRows(target).first()).toBeVisible();
}

/** Selects the movements whose descriptions are `names`, the first by click
 * and the others with Ctrl. */
async function selectMovements(target: Page, names: readonly string[]) {
  for (const [index, name] of names.entries())
    await rowOf(target, name)
      .locator("[data-column=status]")
      .click(index === 0 ? {} : { modifiers: ["Control"] });
  await expect(page(target).locator(".ledger-count")).toContainText(
    label("desktop.ledger.selected", { count: names.length }),
  );
}

async function openSelectionActions(target: Page, count: number) {
  const actions = page(target).locator(".ledger-selection-actions");
  // A visible label that names how many are selected, not an icon alone.
  await expect(actions).toHaveText(
    label("desktop.ledger.selection.actions_count", { count }),
  );
  await actions.click();
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
  await review(target).locator(".ledger-apply-done").click();
}

// Outgoing Business and Mixed movements near the top of the opening period,
// each the only row with its description: a category can be asked for them,
// and the grid keeps all of them drawn while they are selected. None of them
// holds the category the test asks for.
const MOVEMENTS = [
  "CUOTA AUTONOMOS TGSS",
  "COMISION MANTENIMIENTO CUENTA",
  "FIBRA HOGAR ALBOR",
] as const;
const CHOSEN = "desktop.ledger.category.material_oficina";

test("one category is asked for the selected movements, reviewed as one change, saved on all of them, and removed from two", async ({
  page: target,
}) => {
  await openLedger(target);
  await selectMovements(target, MOVEMENTS);
  await openSelectionActions(target, 3);
  const menu = target.getByRole("menu");
  const asked = menu.getByRole("menuitem", {
    name: `${label("desktop.ledger.group.category")}…`,
    exact: true,
  });
  await expect(asked).toBeVisible();
  await expect(
    menu.getByRole("menuitem", {
      name: label("desktop.ledger.selection.clear_category"),
      exact: true,
    }),
  ).toBeVisible();
  await asked.click();

  const dialog = classify(target);
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading")).toHaveText(
    label("desktop.ledger.classify.title_category", { count: 3 }),
  );
  await dialog.locator(".ledger-classify-category").click();
  await target.keyboard.type(label(CHOSEN));
  await target.keyboard.press("Enter");
  await expect(target.locator("[data-slot=combobox]")).toBeHidden();
  await dialog.locator(".ledger-classify-stage").click();
  await expect(dialog).toHaveCount(0);

  // All three are staged at once, and the page says so.
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.classify.staged_category", {
      category: label(CHOSEN),
      count: 3,
    }),
  );
  for (const name of MOVEMENTS)
    await expect(
      categoryOf(rowOf(target, name)).locator("[data-staged]"),
    ).toContainText(label(CHOSEN));

  // The review holds one category change, over three movements.
  await openReview(target);
  const summary = review(target).locator(".ledger-summary tbody tr");
  await expect(summary).toHaveCount(3);
  for (const change of await summary.all())
    await expect(change).toContainText(label(CHOSEN));
  await expect(review(target).locator(".ledger-review-rows-toggle")).toHaveText(
    `${label("desktop.ledger.apply.summary_movements")} · 3`,
  );
  await save(target);

  for (const name of MOVEMENTS)
    await expect(categoryOf(rowOf(target, name))).toContainText(label(CHOSEN));
  await expect(tray(target)).toHaveCount(0);

  // The category is removed from two of them in one step.
  await selectMovements(target, MOVEMENTS.slice(0, 2));
  await openSelectionActions(target, 2);
  await target
    .getByRole("menu")
    .getByRole("menuitem", {
      name: label("desktop.ledger.selection.clear_category"),
      exact: true,
    })
    .click();
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.classify.cleared_category", { count: 2 }),
  );
  await openReview(target);
  await save(target);
  for (const name of MOVEMENTS.slice(0, 2))
    await expect(categoryOf(rowOf(target, name))).not.toContainText(
      label(CHOSEN),
    );
  await expect(categoryOf(rowOf(target, MOVEMENTS[2]))).toContainText(
    label(CHOSEN),
  );
});

test("a personal movement in the selection is reported, never given a category", async ({
  page: target,
}) => {
  await openLedger(target);
  await selectMovements(target, [
    "CUOTA AUTONOMOS TGSS",
    "RESTAURANTE LA ALACENA",
  ]);
  await openSelectionActions(target, 2);
  await target
    .getByRole("menu")
    .getByRole("menuitem", {
      name: `${label("desktop.ledger.group.category")}…`,
      exact: true,
    })
    .click();
  const dialog = classify(target);
  await expect(dialog).toContainText(
    label("desktop.ledger.classify.skipped", { count: 1 }),
  );
  await expect(dialog.getByRole("heading")).toHaveText(
    label("desktop.ledger.classify.title_category", { count: 1 }),
  );
});
