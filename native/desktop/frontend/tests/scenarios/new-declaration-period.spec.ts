import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import type { ModeloDeclarationsListProjectionV1 } from "../../src/shell/modeloContract/modeloDeclarations";
import { MODELO_FIXTURES } from "../support/windowFixtures";

// The new-declaration dialog offers the addresses the backend serves and
// starts on the one it suggests. A modelo the backend suggests no address for
// starts with nothing chosen: the window never picks a period of its own, so a
// quarterly filer is never started on the first month the list happens to hold.

const served = JSON.parse(
  readFileSync(new URL("declarations-en.json", MODELO_FIXTURES), "utf8"),
) as ModeloDeclarationsListProjectionV1;

const dialog = (target: Page) => target.locator(".new-declaration");

async function choose(target: Page, modelo: string) {
  await target.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=default",
  );
  await target.locator("[data-rail=declarations]").click();
  await target.locator(".declarations-page .declarations-new").click();
  await dialog(target)
    .locator(".new-declaration-modelo")
    .filter({ hasText: modelo })
    .first()
    .click();
}

test("a modelo without a served suggestion starts with no period chosen", async ({
  page: target,
}) => {
  const unsuggested = [
    ...new Set(served.creation_targets.map((x) => x.modelo)),
  ].find((modelo) =>
    served.creation_targets.every((x) => x.modelo !== modelo || !x.suggested),
  );
  // The recorded list must hold a modelo the backend suggests nothing for;
  // should it ever suggest one for every modelo, this case needs a list that
  // does not.
  expect(unsuggested).toBeDefined();
  await choose(target, unsuggested!);
  await expect(
    dialog(target).locator(".new-declaration-period"),
  ).not.toHaveCount(0);
  await expect(
    dialog(target).locator(".new-declaration-period[aria-checked=true]"),
  ).toHaveCount(0);
  await expect(
    dialog(target).locator(".new-declaration-submit"),
  ).toBeDisabled();
});

test("the served suggestion is the period the dialog starts on", async ({
  page: target,
}) => {
  const suggested = served.creation_targets.find((x) => x.suggested);
  expect(suggested).toBeDefined();
  await choose(target, suggested!.modelo);
  await expect(
    dialog(target).locator(".new-declaration-period[aria-checked=true]"),
  ).toContainText(suggested!.period_words);
});
