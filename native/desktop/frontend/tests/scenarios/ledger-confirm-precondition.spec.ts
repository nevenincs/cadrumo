import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { label } from "../support/strings";
import { row } from "../support/userProfilePage";
import { windowFixture } from "../support/windowFixtures";

// A profile that states no fiscal-address postcode cannot confirm any
// invoice. The queue says so once, in the backend's words, with the step that
// supplies the fact; a row with nothing of its own to answer is not called
// ready; a confirmation refused for it shows the same words and the same step;
// and the step opens the profile on that detail. Every word and address below
// is the backend's, read from the recorded fixture. Every value is synthetic.

/** What the backend serves for a profile without the postcode, as the
 * generated fixture records it. */
const SERVED = (
  JSON.parse(
    readFileSync(
      windowFixture("ledger-served-words", "ledgerServedWords"),
      "utf8",
    ),
  ) as {
    confirm_precondition: {
      refusal: Record<string, string>;
      step: Record<string, string>;
      path: Record<string, string>;
    };
  }
).confirm_precondition;
const WORDS = SERVED.refusal.en!;
const STEP = SERVED.step.en!;
const PATH = SERVED.path.en!;

const DOMESTIKA = "factura-domestika-lettering.pdf";

const section = (target: Page) => target.locator(".ledger-documents");
const draft = (target: Page) => section(target).locator(".ledger-draft");
const precondition = (target: Page) =>
  section(target).locator(".ledger-review-precondition");

async function openDocuments(target: Page, shape: string) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&ledger=${shape}`,
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-movements")).toBeVisible();
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.documents") })
    .click();
  await expect(section(target)).toBeVisible();
}

const queueItem = (target: Page, name: string) =>
  section(target).locator(".ledger-review-item").filter({ hasText: name });

test("a profile without the postcode is said once above the queue, with the step that supplies it", async ({
  page: target,
}) => {
  await openDocuments(target, "missing_postcode");
  await expect(precondition(target)).toHaveCount(1);
  await expect(precondition(target)).toContainText(WORDS);
  await expect(
    precondition(target).getByRole("button", { name: STEP, exact: true }),
  ).toBeVisible();
  // A reading with no finding of its own is not called ready while no
  // confirmation can succeed.
  await expect(queueItem(target, DOMESTIKA)).toContainText(WORDS);
  await expect(queueItem(target, DOMESTIKA)).not.toContainText(
    label("desktop.ledger.documents.ready_to_confirm"),
  );
});

test("the step above the queue opens the profile on the postcode", async ({
  page: target,
}) => {
  await openDocuments(target, "missing_postcode");
  await precondition(target)
    .getByRole("button", { name: STEP, exact: true })
    .click();
  const profile = target.locator(".user-profile-page");
  await expect(profile).toBeVisible();
  // The detail's own row takes the focus: one door, no dialog in the way.
  await expect(row(profile, PATH)).toBeFocused();
  await expect(target.getByRole("dialog")).toHaveCount(0);
});

test("a confirmation refused for the postcode shows the served words and a step to the profile field", async ({
  page: target,
}) => {
  await openDocuments(target, "missing_postcode");
  await queueItem(target, DOMESTIKA).click();
  await expect(
    draft(target).getByRole("heading", { name: DOMESTIKA }),
  ).toBeVisible();
  // The reading states the side and the country, so nothing else holds it.
  await draft(target).locator(".ledger-draft-confirm").click();
  const refused = draft(target)
    .getByRole("alert")
    .filter({ hasText: label("desktop.ledger.documents.not_done") });
  await expect(refused).toBeVisible();
  await expect(refused.locator(".ledger-draft-refusal")).toHaveText(WORDS);
  const door = refused.getByRole("button", { name: STEP, exact: true });
  await expect(door).toBeVisible();
  await door.click();
  const profile = target.locator(".user-profile-page");
  await expect(profile).toBeVisible();
  await expect(row(profile, PATH)).toBeFocused();
  await expect(target.getByRole("dialog")).toHaveCount(0);
});

test("a profile that states the postcode shows no precondition and calls a clean reading ready", async ({
  page: target,
}) => {
  await openDocuments(target, "documents");
  await expect(
    section(target).locator(".ledger-review-item").first(),
  ).toBeVisible();
  await expect(precondition(target)).toHaveCount(0);
  await expect(queueItem(target, DOMESTIKA)).toContainText(
    label("desktop.ledger.documents.ready_to_confirm"),
  );
  await expect(queueItem(target, DOMESTIKA)).not.toContainText(WORDS);
});
