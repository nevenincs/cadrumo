import { expect, test, type Locator, type Page } from "@playwright/test";
import { captureUnrecordedQuestions } from "../support/stagedCheckCapture";
import { label } from "../support/strings";

// The inspector's Documents section over the scenario's ledger: while a
// movement has no purchase invoice, the person says what a document is
// before it is staged, so no file becomes the purchase invoice unasked; a
// file picked first waits for that choice; and the save's result counts and
// lists that change as the review did.

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const panel = (target: Page) => target.locator("aside.ledger-panel");
const index = (target: Page) => panel(target).locator(".ledger-jump-index");
const body = (target: Page) => panel(target).locator(".ledger-inspector-body");
const tray = (target: Page) => target.locator(".ledger-tray");
const review = (target: Page) => target.locator(".ledger-review");

async function openLedger(target: Page) {
  await captureUnrecordedQuestions(target);
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(dataRows(target).first()).toBeVisible();
}

const rowOf = (target: Page, text: string) =>
  dataRows(target)
    .filter({
      has: target.locator("[data-column=description]", { hasText: text }),
    })
    .first();
const cellOf = (row: Locator, column: string) =>
  row.locator(`[data-column=${column}]`);

/** Selects the movement, opens the inspector and goes to its Documents. */
async function documentsOf(target: Page, text: string) {
  await cellOf(rowOf(target, text), "status").click();
  if (!(await panel(target).isVisible()))
    await target.keyboard.press("Alt+KeyI");
  await expect(panel(target).locator(".ledger-inspector h2")).toContainText(
    text,
  );
  const entry = index(target).locator("[data-section=documents]");
  if (await entry.count()) await entry.click();
  else {
    await index(target).locator(".ledger-jump-more").click();
    await target
      .getByRole("menuitem", {
        name: label("desktop.ledger.inspector.section.documents"),
        exact: true,
      })
      .click();
  }
  return body(target).locator("[data-section-body=documents]");
}

const kinds = (section: Locator) =>
  section.getByRole("radiogroup", {
    name: label("desktop.ledger.inspector.documents.kind.label"),
  });
const kind = (section: Locator, choice: "purchase" | "other") =>
  kinds(section).getByRole("radio", {
    name: label(`desktop.ledger.inspector.documents.kind.${choice}`),
  });
const addFile = (section: Locator) =>
  section.getByRole("button", {
    name: label("desktop.ledger.inspector.documents.add_file"),
  });

test("Documents asks what a document is before staging it, and never makes a file the purchase invoice unasked", async ({
  page: target,
}) => {
  await openLedger(target);
  const section = await documentsOf(target, "PAPELERIA TRAZO");
  const attach = section.getByRole("button", {
    name: label("desktop.ledger.inspector.documents.attach_existing"),
  });
  // Nothing is chosen for the person: an existing document waits for a
  // kind, and a file from this computer waits beside the choice.
  await expect(
    kinds(section).getByRole("radio", { checked: true }),
  ).toHaveCount(0);
  await expect(attach).toBeDisabled();
  await expect(section).toContainText(
    label("desktop.ledger.inspector.documents.kind.choose"),
  );
  await addFile(section).click();
  const pending = section.locator(".ledger-document-pending");
  await expect(pending).toContainText("ticket-gasolinera-ruta7.jpg");
  await expect(pending).toHaveAttribute("data-probe", "read");
  await expect(section).not.toContainText(
    label("desktop.ledger.inspector.documents.adding_other", {
      file: "ticket-gasolinera-ruta7.jpg",
    }),
  );

  await kind(section, "other").click();
  await expect(section).toContainText(
    label("desktop.ledger.inspector.documents.adding_other", {
      file: "ticket-gasolinera-ruta7.jpg",
    }),
  );
  await expect(pending).toHaveCount(0);
  // The choice served one document: the next one is asked again.
  await expect(
    kinds(section).getByRole("radio", { checked: true }),
  ).toHaveCount(0);

  await kind(section, "purchase").click();
  await addFile(section).click();
  await expect(section).toContainText(
    label("desktop.ledger.inspector.documents.adding_purchase", {
      file: "ticket-gasolinera-ruta7.jpg",
    }),
  );
  // With a purchase invoice staged, any further document is another one.
  await expect(kinds(section)).toHaveCount(0);
  await expect(addFile(section)).toBeEnabled();
});

test("a document from this computer saves as one change, counted and listed as the review counted it", async ({
  page: target,
}) => {
  await openLedger(target);
  const section = await documentsOf(target, "PAPELERIA TRAZO");
  await kind(section, "purchase").click();
  await addFile(section).click();
  await expect(section).toContainText(
    label("desktop.ledger.inspector.documents.adding_purchase", {
      file: "ticket-gasolinera-ruta7.jpg",
    }),
  );

  await tray(target).locator(".ledger-tray-review").click();
  await expect(review(target)).toBeVisible();
  const save = review(target).locator(".ledger-apply-save");
  await expect(save).toHaveText(
    label("desktop.ledger.apply.save", { count: 1 }),
  );
  await expect(review(target)).toContainText(
    label("desktop.ledger.apply.action.attach_file_purchase", {
      name: "ticket-gasolinera-ruta7.jpg",
    }),
  );
  await save.click();
  await expect(review(target).locator(".ledger-apply-done")).toBeVisible({
    timeout: 20_000,
  });
  // The evidence add and its attach are one change: one saved, one listed.
  await expect(review(target).locator(".ledger-apply-headline")).toHaveText(
    `${label("desktop.ledger.apply.tally.applied")} · 1`,
  );
  const listed = review(target).locator(".ledger-outcomes [data-outcome]");
  await expect(listed).toHaveCount(1);
  await expect(listed).toHaveAttribute("data-outcome", "applied");
  await expect(listed).toContainText(
    label("desktop.ledger.apply.action.attach_file_purchase", {
      name: "ticket-gasolinera-ruta7.jpg",
    }),
  );
});
