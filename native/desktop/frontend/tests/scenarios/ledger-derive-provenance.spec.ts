import { expect, test, type Page } from "@playwright/test";
import { captureUnrecordedQuestions } from "../support/stagedCheckCapture";
import { label } from "../support/strings";

// The IVA derivation of the inspector over the scenario's ledger: staged with
// a classification it saves as one plan with nothing held, and once saved the
// figures say the product worked them out while the classification stays the
// person's.

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const panel = (target: Page) => target.locator("aside.ledger-panel");
const body = (target: Page) => panel(target).locator(".ledger-inspector-body");
const review = (target: Page) => target.locator(".ledger-review");

async function openLedger(target: Page) {
  await captureUnrecordedQuestions(target);
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(dataRows(target).first()).toBeVisible();
}

async function inspect(target: Page, text: string) {
  await openLedger(target);
  await dataRows(target)
    .filter({
      has: target.locator("[data-column=description]", { hasText: text }),
    })
    .first()
    .locator("[data-column=status]")
    .click();
  if (!(await panel(target).isVisible()))
    await target.keyboard.press("Alt+KeyI");
  await expect(panel(target).locator(".ledger-inspector h2")).toContainText(
    text,
  );
}

const tray = (target: Page) => target.locator(".ledger-tray");
const trayCount = async (target: Page) =>
  Number(
    await tray(target)
      .locator(".ledger-tray-toggle span[aria-hidden=true]")
      .textContent(),
  );

async function choose(target: Page, option: string) {
  const list = target.locator("[data-slot=combobox]");
  await expect(list).toBeVisible();
  await target.keyboard.type(option);
  await list.getByRole("option", { name: option }).first().click();
  await expect(list).toHaveCount(0);
}

test("a derivation staged beside the person's classification saves with nothing held, and its figures are marked calculated", async ({
  page: target,
}) => {
  await inspect(target, "FIBRA HOGAR ALBOR");
  const decision = body(target).locator(".ledger-decision");
  await expect(decision).toContainText(
    label("desktop.ledger.inspector.by.you"),
  );
  await expect(body(target).locator(".ledger-figures-derived")).toHaveCount(0);

  await body(target)
    .locator(".ledger-derive")
    .getByRole("button", {
      name: label("desktop.ledger.inspector.derive.stage"),
    })
    .click();
  await target.locator(".ledger-tray .ledger-tray-review").click();
  const save = review(target).locator(".ledger-apply-save");
  await expect(save).toHaveText(
    label("desktop.ledger.apply.save", { count: 1 }),
  );
  await expect(save).not.toHaveAttribute("aria-disabled", "true");
  await expect(review(target)).not.toContainText(
    label("desktop.ledger.apply.held", { count: 1 }),
  );
  await save.click();
  const done = review(target).locator(".ledger-apply-done");
  await expect(done).toBeVisible({ timeout: 20_000 });
  await done.click();

  // The figures say who worked them out; the decision stays the person's.
  await expect(body(target).locator(".ledger-figures-derived")).toHaveCount(3);
  await expect(decision).toContainText(
    label("desktop.ledger.inspector.by.you"),
  );
  const base = body(target).locator("[data-field=taxable_base]");
  // The mark is described, never part of the name.
  await expect(base).toHaveAccessibleName(
    new RegExp(`^${label("desktop.ledger.column.taxable_base")} [0-9.,]+$`),
  );
  await expect(base).toHaveAccessibleDescription(
    new RegExp(label("desktop.ledger.inspector.by.derived")),
  );
});

test("the IVA calculation reads the one IVA category field and follows it", async ({
  page: target,
}) => {
  await inspect(target, "SOFTNUBE IRELAND SUSCRIPCION");
  const derive = body(target).locator(".ledger-derive");
  const stage = derive.getByRole("button", {
    name: label("desktop.ledger.inspector.derive.stage"),
  });
  const field = body(target).locator("[data-field=iva_category]");
  // The calculation has no picker of its own: with no category in the field
  // it asks for one there.
  await expect(derive.getByRole("combobox")).toHaveCount(0);
  await expect(derive.locator("[aria-haspopup=listbox]")).toHaveCount(0);
  await expect(stage).toBeDisabled();
  await expect(derive).toContainText(
    label("desktop.ledger.inspector.derive.choose"),
  );
  await derive
    .getByRole("button", { name: label("desktop.ledger.column.iva_category") })
    .click();
  await expect(field).toBeFocused();
  await field.click();
  await choose(target, label("desktop.ledger.iva_category.domestic_general"));
  await expect(stage).toBeEnabled();
  await stage.click();
  await expect(derive).toContainText(
    label("desktop.ledger.inspector.derive.staged", {
      category: label("desktop.ledger.iva_category.domestic_general"),
    }),
  );
  // The field and the derivation are two staged writes.
  expect(await trayCount(target)).toBe(2);
  // Another category in the field changes the staged derivation.
  await field.click();
  await choose(target, label("desktop.ledger.iva_category.domestic_reduced"));
  await expect(derive).toContainText(
    label("desktop.ledger.inspector.derive.staged", {
      category: label("desktop.ledger.iva_category.domestic_reduced"),
    }),
  );
  expect(await trayCount(target)).toBe(2);
  // Emptying the field leaves nothing to derive from.
  await field.click();
  await choose(target, label("desktop.ledger.inspector.clear"));
  await expect(derive).not.toContainText(
    label("desktop.ledger.inspector.derive.staged", {
      category: label("desktop.ledger.iva_category.domestic_reduced"),
    }),
  );
  await expect(stage).toBeDisabled();
});

test("a field is named by its label and the value it shows, the value it replaces only described, and its list by the label", async ({
  page: target,
}) => {
  await inspect(target, "SOFTNUBE IRELAND SUSCRIPCION");
  const name = label("desktop.ledger.column.iva_category");
  const general = label("desktop.ledger.iva_category.domestic_general");
  const field = body(target).locator("[data-field=iva_category]");
  await expect(
    body(target).locator("dl").getByRole("button", { name, exact: false }),
  ).toHaveCount(1);
  await expect(field).toHaveAccessibleName(
    `${name} ${label("desktop.ledger.inspector.not_set")}`,
  );
  await field.click();
  const list = target.locator("[data-slot=combobox]");
  await expect(list).toBeVisible();
  await expect(list).toHaveAccessibleName(name);
  await expect(target.getByRole("dialog", { name })).toBeVisible();
  await choose(target, general);
  // The name never glues the old value to the new.
  await expect(field).toHaveAccessibleName(`${name} ${general}`);
  await expect(field).toHaveAccessibleDescription(
    new RegExp(label("desktop.ledger.inspector.empty")),
  );
});

test("the classify and leave dialogs offer one Cancel each", async ({
  page: target,
}) => {
  await inspect(target, "PAPELERIA TRAZO");
  await body(target)
    .locator("[data-field=business_classification]")
    .getByRole("radio", {
      name: label("desktop.ledger.classification.business"),
    })
    .click();
  const dialog = target.locator(".ledger-classify");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.ledger.classify.cancel"),
      exact: true,
    }),
  ).toHaveCount(1);
  await target.keyboard.press("Escape");
  // Leaving with the change staged asks in a dialog with one Cancel too.
  await body(target)
    .locator("[data-field=business_classification]")
    .getByRole("radio", {
      name: label("desktop.ledger.classification.personal"),
    })
    .click();
  await target.keyboard.press("Control+Shift+KeyD");
  await expect(
    target.locator(".ledger-leave").getByRole("button", {
      name: label("desktop.ledger.leave.cancel"),
      exact: true,
    }),
  ).toHaveCount(1);
});
