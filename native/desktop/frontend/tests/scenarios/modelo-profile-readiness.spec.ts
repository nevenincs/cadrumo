import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import type { LedgerErrorDetail } from "../../src/shell/ledger";
import { servedNextStep, servedRefusalWords } from "../../src/shell/ledger";
import { label } from "../support/strings";
import { profileSectionTitle } from "../support/profileFixture";
import { MODELO_FIXTURES } from "../support/windowFixtures";

// Creating a declaration for a profile the application will not file for. The
// refusal says why in the application's own words and names one door for
// putting it right; this holds the window to opening that door. Every word and
// every address is the backend's: the spec reads the recorded refusal rather
// than stating a sentence or a field path of its own.

const open = (target: Page, shape: string) =>
  target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=${shape}`,
  );

const declarations = (target: Page) => target.locator(".declarations-page");
const dialog = (target: Page) => target.locator(".new-declaration");
const profile = (target: Page) => target.locator(".user-profile-page");

/** The refusal the scenario settles the creation with, as the backend
 * recorded it. */
const recorded = (shape: string) =>
  JSON.parse(
    readFileSync(new URL(`refusal-${shape}-en.json`, MODELO_FIXTURES), "utf8"),
  ) as LedgerErrorDetail;

const MODELO = "303";

async function refuseCreation(target: Page, shape: string) {
  await open(target, shape);
  await target.locator("[data-rail=declarations]").click();
  await expect(
    declarations(target).locator("[data-kind=data]").first(),
  ).toBeVisible();
  await declarations(target).locator(".declarations-new").click();
  await dialog(target)
    .locator(".new-declaration-modelo")
    .filter({ hasText: MODELO })
    .first()
    .click();
  await dialog(target).locator(".new-declaration-period").first().click();
  await dialog(target).locator(".new-declaration-submit").click();
  return dialog(target).getByRole("alert");
}

test("a creation refused for a profile fact opens where that fact is filled in", async ({
  page: target,
}) => {
  const detail = recorded("profile-field");
  const step = servedNextStep(detail);
  expect(step?.kind).toBe("open_profile_field");
  if (step?.kind !== "open_profile_field") return;

  const alert = await refuseCreation(target, "profile-field");
  // The refusal's own sentence, and the door in the words the backend served.
  await expect(alert).toContainText(servedRefusalWords(detail)!);
  const door = alert.getByRole("button", { name: step.words, exact: true });
  await expect(door).toBeVisible();
  await door.click();

  // The window shows the profile; the dialog is gone, because the step is
  // answered on the page the window moved to. The scenario's profile holds
  // no entry of the section the detail belongs to, so the detail is filled in
  // as that section's first entry, and the entry opens.
  await expect(dialog(target)).toBeHidden();
  await expect(profile(target)).toBeVisible();
  const section = step.path.slice(0, step.path.indexOf("."));
  await expect(
    target.getByRole("dialog", {
      name: profileSectionTitle(section),
      exact: true,
    }),
  ).toBeVisible();
});

test("a creation refused for an undeclared setup opens the profile's completion", async ({
  page: target,
}) => {
  const detail = recorded("profile-setup");
  const step = servedNextStep(detail);
  expect(step?.kind).toBe("complete_profile_setup");
  if (step?.kind !== "complete_profile_setup") return;

  const alert = await refuseCreation(target, "profile-setup");
  await expect(alert).toContainText(servedRefusalWords(detail)!);
  const door = alert.getByRole("button", { name: step.words, exact: true });
  await expect(door).toBeVisible();
  await door.click();

  await expect(dialog(target)).toBeHidden();
  await expect(profile(target)).toBeVisible();
  // The completion is the profile's own action; the page is left on it, with
  // the action the refusal named among the profile's actions.
  await profile(target)
    .getByRole("button", {
      name: label("desktop.profile.action.menu"),
      exact: true,
    })
    .click();
  await expect(
    target.getByRole("menuitem", {
      name: label("desktop.profile.complete"),
      exact: true,
    }),
  ).toBeVisible();
});

test("a refusal the host reports by rejecting the submission keeps its words and door", async ({
  page: target,
}) => {
  // The host may answer a refused write by rejecting the submission with the
  // settled operation's identity. The window then reads that operation's
  // detail, and shows the same sentence and the same door as a settlement.
  const detail = recorded("profile-setup");
  const step = servedNextStep(detail);
  expect(step?.kind).toBe("complete_profile_setup");
  if (step?.kind !== "complete_profile_setup") return;

  const alert = await refuseCreation(target, "profile-setup-rejected");
  await expect(alert).toContainText(servedRefusalWords(detail)!);
  await expect(alert).not.toContainText(
    label("workspace.declarations.list.new.refused"),
  );
  const door = alert.getByRole("button", { name: step.words, exact: true });
  await expect(door).toBeVisible();
  await door.click();
  await expect(dialog(target)).toBeHidden();
  await expect(profile(target)).toBeVisible();
});

test("a refusal naming no door leaves the refusal's words standing alone", async ({
  page: target,
}) => {
  // ANTI-VACUITY: the door is the served step's, not something the dialog
  // draws for every refusal.
  const alert = await refuseCreation(target, "refused");
  await expect(alert).toContainText(
    label("workspace.declarations.list.new.refused"),
  );
  await expect(alert.locator(".new-declaration-refusal-step")).toHaveCount(0);
});
