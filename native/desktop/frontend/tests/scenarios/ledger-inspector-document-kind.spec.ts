import { expect, test, type Locator, type Page } from "@playwright/test";
import { captureUnrecordedQuestions } from "../support/stagedCheckCapture";
import { label } from "../support/strings";

// The inspector's Documents section, adding a file from this computer to a
// movement with no purchase invoice before saying what it is. The ledger
// reads the file's bytes first: a structured e-invoice is offered as a
// purchase invoice, shown as the ledger's proposal with one control that
// makes it the person's choice; any other file is offered no kind. Nothing
// is chosen or staged for the person, who may still choose the other kind.
// Every file is synthetic.

const E_INVOICE = "factura-estudio-lumen.xml";
const PHOTO = "ticket-gasolinera-ruta7.jpg";

const ledgerPage = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => ledgerPage(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const panel = (target: Page) => target.locator("aside.ledger-panel");
const index = (target: Page) => panel(target).locator(".ledger-jump-index");
const body = (target: Page) => panel(target).locator(".ledger-inspector-body");

/** Opens the scenario ledger with the documents dialog offering `name`. */
async function openLedger(target: Page, name: string) {
  await captureUnrecordedQuestions(target);
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.evaluate((offered) => {
    window.__fixtureLedgerFiles = {
      offered: (purpose) => (purpose === "documents" ? [offered] : undefined),
    };
  }, name);
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(dataRows(target).first()).toBeVisible();
}

/** Selects the movement, opens the inspector and goes to its Documents. */
async function documentsOf(target: Page, text: string) {
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
const proposal = (section: Locator) =>
  section.locator(".ledger-document-kind-proposal");

test("an e-invoice from this computer is proposed as the purchase invoice, and taking the proposal is the person's choice", async ({
  page: target,
}) => {
  await openLedger(target, E_INVOICE);
  const section = await documentsOf(target, "PAPELERIA TRAZO");
  await addFile(section).click();

  const pending = section.locator(".ledger-document-pending");
  await expect(pending).toContainText(E_INVOICE);
  await expect(proposal(section)).toContainText(
    label("desktop.ledger.inspector.documents.kind.proposal"),
  );
  await expect(section).toContainText(
    label("desktop.ledger.inspector.documents.kind.pending", {
      file: E_INVOICE,
    }),
  );
  // The proposal is shown, never applied: no kind is chosen and nothing is
  // staged until the person acts.
  await expect(
    kinds(section).getByRole("radio", { checked: true }),
  ).toHaveCount(0);
  await expect(section).not.toContainText(
    label("desktop.ledger.inspector.documents.adding_purchase", {
      file: E_INVOICE,
    }),
  );

  await proposal(section)
    .getByRole("button", {
      name: label("desktop.ledger.inspector.documents.kind.use_proposal"),
    })
    .click();
  await expect(section).toContainText(
    label("desktop.ledger.inspector.documents.adding_purchase", {
      file: E_INVOICE,
    }),
  );
  await expect(pending).toHaveCount(0);
  // With the purchase invoice staged, the choice is no longer asked.
  await expect(kinds(section)).toHaveCount(0);
});

test("the person may choose the other kind over the proposal", async ({
  page: target,
}) => {
  await openLedger(target, E_INVOICE);
  const section = await documentsOf(target, "PAPELERIA TRAZO");
  await addFile(section).click();
  await expect(proposal(section)).toBeVisible();

  await kind(section, "other").click();
  await expect(section).toContainText(
    label("desktop.ledger.inspector.documents.adding_other", {
      file: E_INVOICE,
    }),
  );
  await expect(section.locator(".ledger-document-pending")).toHaveCount(0);
});

test("a file whose bytes support no kind is offered none, and a dropped file stages nothing", async ({
  page: target,
}) => {
  await openLedger(target, PHOTO);
  const section = await documentsOf(target, "PAPELERIA TRAZO");
  await addFile(section).click();

  const pending = section.locator(".ledger-document-pending");
  await expect(pending).toHaveAttribute("data-probe", "read");
  await expect(pending).toContainText(PHOTO);
  await expect(proposal(section)).toHaveCount(0);

  await pending
    .getByRole("button", { name: label("desktop.ledger.inspector.drop") })
    .click();
  await expect(pending).toHaveCount(0);
  await expect(section).not.toContainText(
    label("desktop.ledger.inspector.documents.adding_other", { file: PHOTO }),
  );
  await expect(section).not.toContainText(
    label("desktop.ledger.inspector.documents.adding_purchase", {
      file: PHOTO,
    }),
  );
  await expect(section).toContainText(
    label("desktop.ledger.inspector.documents.kind.choose"),
  );
});
