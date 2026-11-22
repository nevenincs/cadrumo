import { expect, test, type Locator, type Page } from "@playwright/test";
import { captureUnrecordedQuestions } from "../support/stagedCheckCapture";
import { label } from "../support/strings";

// Batch editing over the scenario's ledger: a range and the shown rows
// selected, one category saved on several movements by a batch edit whose
// preview answers for each row before Save, a partial answer shown as it is,
// properties copied from one movement and pasted onto a selection, the undo of
// a saved batch, and the same work by keyboard alone.

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const panel = (target: Page) => target.locator("aside.ledger-panel");
const tray = (target: Page) => target.locator(".ledger-tray");
const review = (target: Page) => target.locator(".ledger-review");
const count = (target: Page) => page(target).locator(".ledger-count");
const classify = (target: Page) => target.locator(".ledger-classify");

const rowOf = (target: Page, text: string) =>
  dataRows(target)
    .filter({
      has: target.locator("[data-column=description]", { hasText: text }),
    })
    .first();
const categoryOf = (row: Locator) => row.locator("[data-column=category]");
const keyOf = async (row: Locator) => (await row.getAttribute("data-key"))!;

const controls = {
  editElsewhere: (target: Page, id: string, field: string, value: string) =>
    target.evaluate(
      ([key, name, set]) =>
        window.__scenarioLedger!.editElsewhere(key!, name!, set!),
      [id, field, value] as const,
    ),
  sealElsewhere: (target: Page, id: string) =>
    target.evaluate((key) => window.__scenarioLedger!.sealElsewhere(key), id),
  holdPreviews: (target: Page) =>
    target.evaluate(() => window.__scenarioLedger!.holdPreviews()),
  releasePreviews: (target: Page) =>
    target.evaluate(() => window.__scenarioLedger!.releasePreviews()),
  requests: (target: Page, definition: string) =>
    target.evaluate(
      (name) => window.__scenarioLedger!.requests(name),
      definition,
    ),
};

async function openLedger(target: Page) {
  await captureUnrecordedQuestions(target);
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(dataRows(target).first()).toBeVisible();
}

async function selectMovements(target: Page, names: readonly string[]) {
  for (const [index, name] of names.entries())
    await rowOf(target, name)
      .locator("[data-column=status]")
      .click(index === 0 ? {} : { modifiers: ["Control"] });
  await expect(count(target)).toContainText(
    names.length === 1
      ? label("desktop.ledger.selected_one")
      : label("desktop.ledger.selected", { count: names.length }),
  );
}

/** Asks one category for the selected movements from the selection actions. */
async function stageCategory(target: Page, selected: number, key: string) {
  const actions = page(target).locator(".ledger-selection-actions");
  await expect(actions).toHaveText(
    label("desktop.ledger.selection.actions_count", { count: selected }),
  );
  await actions.click();
  await target
    .getByRole("menu")
    .getByRole("menuitem", {
      name: `${label("desktop.ledger.group.category")}…`,
      exact: true,
    })
    .click();
  const dialog = classify(target);
  await dialog.locator(".ledger-classify-category").click();
  await target.keyboard.type(label(key));
  await target.keyboard.press("Enter");
  await expect(target.locator("[data-slot=combobox]")).toBeHidden();
  await dialog.locator(".ledger-classify-stage").click();
  await expect(dialog).toHaveCount(0);
}

async function openReview(target: Page) {
  await tray(target).locator(".ledger-tray-review").click();
  await expect(review(target)).toBeVisible();
}

/** The review once the ledger has said what the batch would do. */
async function previewed(target: Page) {
  const counts = review(target).locator(".ledger-batch-counts");
  await expect(counts).toBeVisible();
  return counts;
}

async function saveAndWait(target: Page) {
  const save = review(target).locator(".ledger-apply-save");
  await expect(save).not.toHaveAttribute("aria-disabled", "true");
  await save.click();
  await expect(review(target).locator(".ledger-apply-done")).toBeVisible({
    timeout: 20_000,
  });
}

const MOVEMENTS = [
  "CUOTA AUTONOMOS TGSS",
  "COMISION MANTENIMIENTO CUENTA",
  "FIBRA HOGAR ALBOR",
] as const;
const CHOSEN = "desktop.ledger.category.material_oficina";
const PASTE_SOURCE = "COMISION MANTENIMIENTO CUENTA";
const PASTE_TARGETS = [
  "CUOTA AUTONOMOS TGSS",
  "FIBRA HOGAR ALBOR",
  "SOFTNUBE IRELAND SUSCRIPCION",
] as const;
const COPIED = "desktop.ledger.category.gastos_bancarios";

test("Shift selects a range of movements, and the header box selects every shown one", async ({
  page: target,
}) => {
  await openLedger(target);
  await dataRows(target).nth(0).locator("[data-column=status]").click();
  await dataRows(target)
    .nth(3)
    .locator("[data-column=status]")
    .click({ modifiers: ["Shift"] });
  await expect(count(target)).toContainText(
    label("desktop.ledger.selected", { count: 4 }),
  );
  const shown = await dataRows(target).count();
  await grid(target)
    .getByRole("checkbox", { name: label("desktop.ledger.select.shown") })
    .click();
  await expect(count(target)).not.toContainText(
    label("desktop.ledger.selected", { count: 4 }),
  );
  const box = grid(target).getByRole("checkbox", {
    name: label("desktop.ledger.select.shown"),
  });
  await expect(box).toBeChecked();
  expect(shown).toBeGreaterThan(4);
});

test("one category for several movements is saved by one batch edit whose preview answered for every row first", async ({
  page: target,
}) => {
  await openLedger(target);
  await selectMovements(target, MOVEMENTS);
  await stageCategory(target, 3, CHOSEN);
  await openReview(target);
  await expect(await previewed(target)).toHaveText(
    label("desktop.ledger.batch.count.applied", { count: 3 }),
  );
  // Nothing was written by the preview: the grid still holds the stored
  // categories under the staged ones.
  expect(await controls.requests(target, "ledger.update.batch")).toEqual([]);
  const previews = await controls.requests(
    target,
    "ledger.update.batch.preview",
  );
  expect(previews.length).toBeGreaterThan(0);

  await saveAndWait(target);
  const written = await controls.requests(target, "ledger.update.batch");
  expect(written).toHaveLength(1);
  expect(typeof written[0]!.reviewed_plan_digest).toBe("string");
  expect((written[0]!.rows as unknown[]).length).toBe(3);
  // The CSV classification is not used for what a batch carries.
  expect(await controls.requests(target, "ledger.classify.bulk")).toEqual([]);
  await expect(review(target).locator(".ledger-batch-written")).toHaveText(
    label("desktop.ledger.batch.written.applied", { count: 3 }),
  );
  await review(target).locator(".ledger-apply-done").click();
  for (const name of MOVEMENTS)
    await expect(categoryOf(rowOf(target, name))).toContainText(label(CHOSEN));
  await expect(tray(target)).toHaveCount(0);
});

test("a movement changed and one sealed while the preview was asked are shown apart, and only the others are saved", async ({
  page: target,
}) => {
  await openLedger(target);
  const keys = await Promise.all(
    MOVEMENTS.map((name) => keyOf(rowOf(target, name))),
  );
  await selectMovements(target, MOVEMENTS);
  await stageCategory(target, 3, CHOSEN);
  await controls.holdPreviews(target);
  await openReview(target);
  await expect(
    review(target).locator(".ledger-batch-previewing"),
  ).toBeVisible();
  // Saving waits for the ledger's answer, and says so.
  await expect(review(target).locator(".ledger-apply-save")).toHaveAttribute(
    "aria-disabled",
    "true",
  );
  await controls.editElsewhere(target, keys[1]!, "notes", "Revisado fuera");
  await controls.sealElsewhere(target, keys[2]!);
  await controls.releasePreviews(target);

  const counts = await previewed(target);
  await expect(counts).toContainText(
    label("desktop.ledger.batch.count.applied", { count: 1 }),
  );
  await expect(counts).toContainText(
    label("desktop.ledger.batch.count.refused", { count: 1 }),
  );
  await expect(counts).toContainText(
    label("desktop.ledger.batch.count.conflict", { count: 1 }),
  );
  const unwritten = review(target).locator(".ledger-batch-unwritten");
  await expect(
    unwritten.locator("[data-cause=changed_since_seen]"),
  ).toContainText(label("desktop.ledger.apply.refusal.changed_since_seen"));
  await expect(unwritten.locator("[data-cause=sealed]")).toBeVisible();

  await saveAndWait(target);
  await expect(review(target).locator(".ledger-batch-written")).toContainText(
    label("desktop.ledger.batch.written.applied", { count: 1 }),
  );
  // The partial outcome is shown, with a way to read the ledger again.
  await expect(
    review(target).locator(".ledger-apply-refused-reread"),
  ).toBeVisible();
  await review(target).locator(".ledger-apply-done").click();
  await expect(categoryOf(rowOf(target, MOVEMENTS[0]))).toContainText(
    label(CHOSEN),
  );
  // What was not written stays in the changes.
  await expect(tray(target)).toBeVisible();
});

test("a batch that meets another plan than the one reviewed writes nothing, shows the fresh plan and asks for a new Save", async ({
  page: target,
}) => {
  await openLedger(target);
  const first = await keyOf(rowOf(target, MOVEMENTS[0]));
  await selectMovements(target, MOVEMENTS);
  await stageCategory(target, 3, CHOSEN);
  await openReview(target);
  await previewed(target);
  await controls.editElsewhere(target, first, "notes", "Otra ventana");
  await saveAndWait(target);
  await expect(review(target).locator(".ledger-batch-written")).toHaveCount(0);
  await expect(review(target)).toContainText(
    label("desktop.ledger.apply.refusal.plan_changed"),
  );
  await review(target).locator(".ledger-apply-refused-reread").click();
  // The review reads the ledger again and previews the plan as it now is:
  // every row still to change, so the refused write changed none.
  await expect(await previewed(target)).toHaveText(
    label("desktop.ledger.batch.count.applied", { count: 3 }),
  );
  await saveAndWait(target);
  await expect(review(target).locator(".ledger-batch-written")).toHaveText(
    label("desktop.ledger.batch.written.applied", { count: 3 }),
  );
});

test("properties copied from one movement are pasted onto a selection through the preview, and Cancel changes nothing", async ({
  page: target,
}) => {
  await openLedger(target);
  // The source holds a category none of the movements it is pasted onto has.
  await rowOf(target, PASTE_SOURCE).locator("[data-column=status]").click();
  if (!(await panel(target).isVisible()))
    await target.keyboard.press("Alt+KeyI");
  await panel(target)
    .getByRole("button", { name: label("desktop.ledger.inspector.actions") })
    .click();
  await target
    .getByRole("menuitem", {
      name: `${label("desktop.ledger.properties.copy_open")}…`,
    })
    .click();
  const copy = target.locator(".ledger-copy-properties");
  await expect(copy.getByRole("heading")).toHaveText(
    label("desktop.ledger.properties.copy_title"),
  );
  for (const group of [
    "classification",
    "iva",
    "irpf",
    "counterparty",
    "notes",
    "group",
  ])
    await expect(copy.locator(`[data-property-group=${group}]`)).toBeVisible();
  // Only the category is copied.
  for (const box of await copy.locator("[data-copy-field]").all())
    if ((await box.getAttribute("data-copy-field")) !== "category_id")
      await box.uncheck();
  await copy.locator("[data-copy-field=category_id]").check();
  await copy.locator(".ledger-copy-properties-copy").click();
  await expect(copy).toHaveCount(0);

  await selectMovements(target, PASTE_TARGETS);
  const open = panel(target).locator(".ledger-paste-properties-open");
  await expect(open).toHaveText(
    label("desktop.ledger.properties.paste_open", { count: 3 }),
  );
  await open.click();
  const paste = target.locator(".ledger-paste-properties");
  await expect(paste.locator(".ledger-batch-counts")).toHaveText(
    label("desktop.ledger.batch.count.applied", { count: 3 }),
  );
  await expect(paste.locator("[data-paste-field=category_id]")).toContainText(
    label(COPIED),
  );
  // Cancel stages nothing.
  await paste
    .getByRole("button", { name: label("desktop.ledger.inspector.cancel") })
    .click();
  await expect(paste).toHaveCount(0);
  await expect(tray(target)).toHaveCount(0);

  await open.click();
  await paste.locator(".ledger-paste-properties-paste").click();
  await expect(paste).toHaveCount(0);
  for (const name of PASTE_TARGETS)
    await expect(
      categoryOf(rowOf(target, name)).locator("[data-staged]"),
    ).toContainText(label(COPIED));
  expect(await controls.requests(target, "ledger.update.batch")).toEqual([]);
});

test("a saved batch is undone by a new batch that writes each row's earlier value back", async ({
  page: target,
}) => {
  await openLedger(target);
  const before = await Promise.all(
    MOVEMENTS.map((name) => categoryOf(rowOf(target, name)).textContent()),
  );
  await selectMovements(target, MOVEMENTS);
  await stageCategory(target, 3, CHOSEN);
  await openReview(target);
  await previewed(target);
  await saveAndWait(target);
  await review(target).locator(".ledger-batch-undo").click();
  // The undo opens the same review over the earlier values.
  await expect(await previewed(target)).toHaveText(
    label("desktop.ledger.batch.count.applied", { count: 3 }),
  );
  await saveAndWait(target);
  await review(target).locator(".ledger-apply-done").click();
  for (const [at, name] of MOVEMENTS.entries())
    await expect(categoryOf(rowOf(target, name))).toHaveText(before[at]!);
  expect(await controls.requests(target, "ledger.update.batch")).toHaveLength(
    2,
  );
});

test("the batch review, its preview and the undo are reached by keyboard alone", async ({
  page: target,
}) => {
  await openLedger(target);
  await selectMovements(target, MOVEMENTS);
  await stageCategory(target, 3, CHOSEN);
  await tray(target).locator(".ledger-tray-review").focus();
  await target.keyboard.press("Enter");
  await expect(review(target)).toBeVisible();
  const counts = await previewed(target);
  // The counts are a live status the screen reader announces.
  await expect(counts).toHaveAttribute("role", "status");
  await expect(
    review(target).getByRole("region", {
      name: label("desktop.ledger.batch.preview_title"),
    }),
  ).toBeVisible();
  const save = review(target).locator(".ledger-apply-save");
  await save.focus();
  await target.keyboard.press("Enter");
  const undo = review(target).locator(".ledger-batch-undo");
  await expect(undo).toBeVisible({ timeout: 20_000 });
  await undo.focus();
  await target.keyboard.press("Enter");
  await expect(await previewed(target)).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(review(target)).toHaveCount(0);
});
