import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { windowFixture } from "../support/windowFixtures";
import { label } from "../support/strings";

// The Documents section on a computer whose local AI is set up but has no
// model picked to read with. The backend serves the refusal's sentence and
// the step to the choice; the window shows both as served, and the control
// the step leads to opens the model picker of the agent column. It offers no
// setup, because nothing is missing from the local AI. Every value is
// synthetic.

/** The sentences the backend serves for a role with no picked reading model,
 * as the generated fixture records them. */
const SERVED = (
  JSON.parse(
    readFileSync(
      windowFixture("ledger-served-words", "ledgerServedWords"),
      "utf8",
    ),
  ) as {
    reading_model: {
      refusal: Record<string, string>;
      step: Record<string, string>;
    };
  }
).reading_model;
const REFUSAL = SERVED.refusal.en!;
const STEP = SERVED.step.en!;

const PLENOIL = "ticket-plenoil-1015.jpg";
const ARROYO = "factura-arroyo-2026-10.pdf";

const section = (target: Page) => target.locator(".ledger-documents");
const draft = (target: Page) => section(target).locator(".ledger-draft");
const picker = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.agent.settings_title") });

async function openDocuments(target: Page) {
  await target.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&ledger=no_reading_model",
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-movements")).toBeVisible();
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.documents") })
    .click();
  await expect(section(target)).toBeVisible();
}

async function choose(target: Page, name: string) {
  await section(target)
    .locator(".ledger-review-item")
    .filter({ hasText: name })
    .click();
  await expect(draft(target).getByRole("heading", { name })).toBeVisible();
}

test("a scan refused for want of a picked model shows the served sentence and a control to the model picker", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, PLENOIL);
  await draft(target)
    .getByRole("button", { name: label("desktop.ledger.documents.read_again") })
    .click();
  const refused = draft(target)
    .getByRole("alert")
    .filter({ hasText: label("desktop.ledger.documents.not_done") });
  await expect(refused).toBeVisible();
  await expect(refused.locator(".ledger-draft-refusal")).toHaveText(REFUSAL);
  // Nothing is missing from the local AI: no setup is offered or opened.
  await expect(refused.locator(".setup-offer")).toHaveCount(0);
  await expect(
    target.getByRole("dialog", { name: label("desktop.setup.title") }),
  ).toHaveCount(0);
  await expect(picker(target)).toHaveCount(0);
  await refused.getByRole("button", { name: STEP, exact: true }).click();
  await expect(picker(target)).toBeVisible();
});

test("a reading that stood on its labels for want of a picked model says so and leads to the model picker", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, ARROYO);
  const unread = draft(target).locator(".ledger-draft-unread");
  await expect(unread).toContainText(label("desktop.ledger.documents.unread"));
  await expect(unread).toContainText(
    label("desktop.ledger.documents.field.retencion_rate"),
  );
  await expect(unread.locator(".ledger-draft-unread-refusal")).toHaveText(
    REFUSAL,
  );
  await expect(unread.locator(".setup-offer")).toHaveCount(0);
  await expect(picker(target)).toHaveCount(0);
  await unread.getByRole("button", { name: STEP, exact: true }).click();
  await expect(picker(target)).toBeVisible();
});
