import { expect, test, type Locator, type Page } from "@playwright/test";
import { captureUnrecordedQuestions } from "../support/stagedCheckCapture";
import { label } from "../support/strings";

// The inspector's Documents section says what the ledger found about each
// document's stored file, checks one not checked yet on request, and lets
// the person take the movement's purchase document back: unlinked, or kept
// on the movement as an ordinary document. A release decided against a
// movement changed since it was opened is refused in the cause's words.

// The seed's stored documents, matched by the start of their file names.
const ARROYO = "factura-arroyo-";
const PLENOIL = "ticket-plenoil-1015.jpg";
const TRAZO = "PAPELERIA TRAZO";
const COWORKING = "COWORKING RIBERA PUESTO FIJO";

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const panel = (target: Page) => target.locator("aside.ledger-panel");
const index = (target: Page) => panel(target).locator(".ledger-jump-index");
const body = (target: Page) => panel(target).locator(".ledger-inspector-body");
const review = (target: Page) => target.locator(".ledger-review");
const search = (target: Page) =>
  page(target).getByRole("searchbox", {
    name: label("desktop.ledger.search.label"),
  });

async function openLedger(target: Page) {
  await captureUnrecordedQuestions(target);
  // The documents shape seeds the stored documents the ledger has not
  // linked yet, ARROYO and PLENOIL among them.
  await target.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&ledger=documents",
  );
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

/** Selects the movement, opens the inspector and goes to its Documents. */
async function documentsOf(target: Page, text: string) {
  await search(target).fill(text);
  await rowOf(target, text).locator("[data-column=status]").click();
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

/** Attaches the ledger's stored document `file`, as the purchase invoice
 * while the movement has none, otherwise as another document. */
async function attachExisting(
  target: Page,
  section: Locator,
  file: string,
  as: "purchase" | "other" | null,
) {
  if (as)
    await section
      .getByRole("radio", {
        name: label(`desktop.ledger.inspector.documents.kind.${as}`),
      })
      .click();
  await section
    .getByRole("button", {
      name: label("desktop.ledger.inspector.documents.attach_existing"),
    })
    .click();
  await target.getByRole("option", { name: file }).first().click();
}

/** Saves what is staged and closes the review. */
async function save(target: Page) {
  await target.locator(".ledger-tray .ledger-tray-review").click();
  // Saving waits until the ledger has said what a batch edit would do.
  await expect(
    review(target).locator(".ledger-apply-save"),
  ).not.toHaveAttribute("aria-disabled", "true");
  await review(target).locator(".ledger-apply-save").click();
  await expect(review(target).locator(".ledger-apply-done")).toBeVisible({
    timeout: 20_000,
  });
  await target.keyboard.press("Escape");
}

/** Links ARROYO, not checked yet, as the purchase invoice of TRAZO's first
 * movement and PLENOIL, which no reader recognises, as another document. */
async function trazoWithDocuments(target: Page) {
  await openLedger(target);
  let section = await documentsOf(target, TRAZO);
  await attachExisting(target, section, ARROYO, "purchase");
  await attachExisting(target, section, PLENOIL, null);
  await save(target);
  section = await documentsOf(target, TRAZO);
  await expect(section.locator(".ledger-purchase-evidence")).toContainText(
    ARROYO,
  );
  return section;
}

const releaseDoor = (section: Locator, disposition: string) =>
  section.locator(`.ledger-purchase-release [data-release=${disposition}]`);

test("each document says what the ledger found about its stored file, and one not checked yet is checked on request", async ({
  page: target,
}) => {
  const section = await trazoWithDocuments(target);
  const purchase = section.locator(".ledger-purchase-evidence");
  const unchecked = purchase.locator("[data-readability=unchecked]");
  await expect(unchecked).toContainText(
    label("desktop.ledger.inspector.documents.readability.unchecked"),
  );
  const unreadable = section
    .locator(".ledger-attachments li", { hasText: PLENOIL })
    .locator("[data-readability=unreadable]");
  await expect(unreadable).toContainText(
    label("desktop.ledger.inspector.documents.readability.unreadable"),
  );
  await expect(unreadable).toContainText(
    label(
      "desktop.ledger.inspector.documents.readability.cause.bytes_readable",
    ),
  );

  const check = unchecked.locator(".ledger-document-check");
  await expect(check).toHaveText(label("desktop.ledger.documents.check"));
  await expect(check).toHaveAttribute(
    "aria-label",
    new RegExp(
      label("desktop.ledger.inspector.documents.readability.check_named", {
        file: ARROYO,
      }).replace(ARROYO, `${ARROYO}.+`),
    ),
  );
  await check.click();
  // The finding is the ledger's, read again: a readable file says no more.
  await expect(purchase.locator("[data-readability]")).toHaveCount(0);
  await expect(purchase).toContainText(ARROYO);
  await expect(unreadable).toBeVisible();
});

test("keeping the purchase document lists it as an ordinary document of the movement", async ({
  page: target,
}) => {
  const section = await trazoWithDocuments(target);
  await expect(releaseDoor(section, "detach")).toHaveText(
    label("desktop.ledger.inspector.documents.release.detach"),
  );
  await releaseDoor(section, "keep_as_document").click();

  await expect(section.locator(".ledger-purchase-evidence")).toHaveCount(0);
  await expect(
    section.locator(".ledger-attachments li", { hasText: ARROYO }),
  ).toBeVisible();
  await expect(
    section.locator(".ledger-attachments li", { hasText: PLENOIL }),
  ).toBeVisible();
});

test("removing the purchase document from the movement unlinks it", async ({
  page: target,
}) => {
  await openLedger(target);
  const section = await documentsOf(target, COWORKING);
  const purchase = section.locator(".ledger-purchase-evidence");
  await expect(purchase).toBeVisible();
  await expect(releaseDoor(section, "detach")).toBeEnabled();

  await releaseDoor(section, "detach").click();

  await expect(purchase).toHaveCount(0);
  await expect(section.locator(".ledger-purchase-release")).toHaveCount(0);
});

test("a release of a movement changed since it was opened is refused with its cause and what to do", async ({
  page: target,
}) => {
  const section = await trazoWithDocuments(target);
  await target.evaluate(
    (description) => window.__scenarioMovements!.change(description),
    TRAZO,
  );

  await releaseDoor(section, "detach").click();

  const refused = section.locator(".ledger-purchase-release [role=alert]");
  await expect(refused).toContainText(
    label("desktop.ledger.documents.not_done"),
  );
  await expect(refused).toContainText(
    label(
      "desktop.ledger.inspector.documents.release.cause.transaction_changed",
    ),
  );
  await expect(refused).toContainText(
    label(
      "desktop.ledger.inspector.documents.release.next_step.reopen_transaction",
    ),
  );
  // Nothing changed: the purchase document is still the movement's.
  await expect(section.locator(".ledger-purchase-evidence")).toContainText(
    ARROYO,
  );
});
