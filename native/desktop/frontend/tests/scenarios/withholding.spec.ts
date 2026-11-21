import { expect, test, type Page } from "@playwright/test";
import { moreViewsButton, openRailView } from "../support/railViews";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { agentTurns, ask, settled } from "../support/agent";
import { windowToast } from "../support/toast";
import { calls, open, startFromDocs } from "../support/scenarioShell";
import { fixtureYear } from "../../src/dev/fixtureDates";

// Withholding is a page of the first pane that draws what the ledger serves
// of the withholding payers took, by ejercicio, and nothing else: the
// certificates under their served amount columns, the statements that an
// income class had none, and the ejercicios the list offers. A read that did
// not answer is told apart from a list that is empty.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

const railButton = moreViewsButton;
const withholdingPage = (target: Page) => target.locator(".withholding-page");
const block = (target: Page, name: string) =>
  withholdingPage(target).locator(`[data-withholding="${name}"]`);
const ejercicioSelect = (target: Page) =>
  withholdingPage(target).getByLabel(label("desktop.withholding.ejercicio"), {
    exact: true,
  });
const listReads = (target: Page) =>
  calls(target, "ledger ledger.retencion_soportada.list");
const absenceReads = (target: Page) =>
  calls(target, "ledger ledger.retencion_soportada.list_absences");

test("the page reads the served ejercicio when it is shown and draws the certificates and the statements as served", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  // Nothing is read for a page nobody is looking at.
  expect(await listReads(target)()).toBe(0);
  await openRailView(target, "desktop.withholding.title");
  await expect(railButton(target)).toHaveAttribute("aria-pressed", "true");
  await expect(target.locator("#tab-docs")).toHaveText(
    label("desktop.withholding.title"),
  );
  const page = withholdingPage(target);
  await expect(page).toBeVisible();
  await expect(page).toBeFocused();
  // The certificate is worded as the ledger served it, under its served
  // amount columns.
  const records = block(target, "records");
  const row = records.locator("tr", { hasText: "Empresa Ejemplo SL" });
  await expect(row).toContainText("Employment income");
  await expect(row).toContainText("Payer's certificate");
  await expect(row).toContainText("30,000.00");
  await expect(row).toContainText("4,500.00");
  for (const served of [
    "Gross cash amount",
    "Withholding",
    "Deductible expenses",
  ])
    await expect(
      records.getByRole("columnheader", { name: new RegExp(`^${served}`) }),
    ).toBeVisible();
  // The statements of the ejercicio, active and withdrawn, in served words.
  const active = block(target, "absences").locator(".withholding-attested tr", {
    hasText: "No professional fees were withheld.",
  });
  await expect(active).toContainText("Economic activity income");
  await expect(active).toContainText("In force");
  const withdrawn = block(target, "withdrawn").locator("tr", {
    hasText: "No dividends were paid.",
  });
  await expect(withdrawn).toContainText("Income from movable capital");
  await expect(withdrawn).toContainText("Withdrawn");
  // Nothing says the lists are empty, and nothing failed.
  await expect(page.locator("[data-withholding-empty]")).toHaveCount(0);
  await expect(page.locator("[data-withholding-failed]")).toHaveCount(0);
  // The ejercicio read is the one the ledger holds today, and both lists
  // were asked once for it.
  await expect(ejercicioSelect(target)).toHaveValue(String(fixtureYear));
  expect(await listReads(target)()).toBe(1);
  expect(await absenceReads(target)()).toBe(1);
});

test("only the ejercicios the list serves are offered, and choosing one reads it again", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.withholding.title");
  await expect(block(target, "records")).toContainText("Empresa Ejemplo SL");
  const served = [fixtureYear - 2, fixtureYear - 1, fixtureYear].map(String);
  await expect(ejercicioSelect(target).locator("option")).toHaveText(served);
  await ejercicioSelect(target).selectOption(String(fixtureYear - 1));
  // That ejercicio holds neither a certificate nor a statement: it is
  // empty, as the list served it, and says which ejercicio it is.
  await expect(
    withholdingPage(target).locator("[data-withholding-empty]"),
  ).toHaveText(
    label("desktop.withholding.empty", { ejercicio: fixtureYear - 1 }),
  );
  await expect(block(target, "records")).toHaveCount(0);
  await expect(
    withholdingPage(target).locator("[data-withholding-failed]"),
  ).toHaveCount(0);
  expect(await listReads(target)()).toBe(2);
  expect(await absenceReads(target)()).toBe(2);
  // The ejercicios on offer are kept, and the one read is the one shown.
  await expect(ejercicioSelect(target)).toHaveValue(String(fixtureYear - 1));
  await expect(ejercicioSelect(target).locator("option")).toHaveText(served);
  await ejercicioSelect(target).selectOption(String(fixtureYear));
  await expect(block(target, "records")).toContainText("Empresa Ejemplo SL");
  expect(await listReads(target)()).toBe(3);
});

test("a list that did not answer says so with its code and is not drawn as empty, nor read again by itself", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await target.evaluate(() =>
    window.__scenarioLedger?.nextReads("ledger.retencion_soportada.list", 1),
  );
  await openRailView(target, "desktop.withholding.title");
  const failed = block(target, "records").locator("[data-withholding-failed]");
  await expect(failed).toHaveAttribute(
    "data-withholding-failed",
    "unavailable",
  );
  await expect(failed).toContainText(
    label("desktop.withholding.failed", { code: "unavailable" }),
  );
  // The statements were read and are drawn; the failed list is not an empty
  // one, and the page is not an empty ejercicio.
  await expect(block(target, "absences")).toContainText(
    "No professional fees were withheld.",
  );
  await expect(
    withholdingPage(target).locator("[data-withholding-empty]"),
  ).toHaveCount(0);
  await expect(block(target, "records").locator("table")).toHaveCount(0);
  expect(await listReads(target)()).toBe(1);
  // Left alone, it is not read again.
  await target.evaluate(
    () => new Promise((resolve) => window.setTimeout(resolve, 600)),
  );
  expect(await listReads(target)()).toBe(1);
  // Asked again once the ledger answers, it shows the certificates.
  await failed
    .getByRole("button", { name: label("desktop.withholding.read_again") })
    .click();
  await expect(block(target, "records")).toContainText("Empresa Ejemplo SL");
  expect(await listReads(target)()).toBe(2);
});

test("a ledger that answers nothing leaves both lists unavailable and offers no ejercicio but the one asked", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in", "&ledger=unavailable");
  await openRailView(target, "desktop.withholding.title");
  for (const name of ["records", "absences"])
    await expect(
      block(target, name).locator("[data-withholding-failed]"),
    ).toHaveAttribute("data-withholding-failed", "unavailable");
  await expect(
    withholdingPage(target).locator("[data-withholding-empty]"),
  ).toHaveCount(0);
  await expect(ejercicioSelect(target)).toBeDisabled();
});

test("the page opens the Ledger's withholding register, where the changes are made", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.withholding.title");
  await expect(block(target, "records")).toContainText("Empresa Ejemplo SL");
  await withholdingPage(target)
    .getByRole("button", { name: label("desktop.withholding.change") })
    .click();
  await expect(target.locator(".ledger-page")).toBeVisible();
  await expect(
    target.locator(".ledger-withholding-class").first(),
  ).toBeVisible();
  await expect(withholdingPage(target)).toHaveCount(0);
});

test("an agent link to the withholding opens it with the keyboard on it and no notice", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await ask(target, "Respóndeme con enlaces");
  await settled(target);
  await agentTurns(target)
    .getByRole("link", { name: "las retenciones", exact: true })
    .click();
  const page = withholdingPage(target);
  await expect(page).toBeVisible();
  await expect(page).toBeFocused();
  await expect(block(target, "records")).toContainText("Empresa Ejemplo SL");
  await expect(windowToast(target)).toHaveText("");
});

for (const language of ["en", "es", "ca", "hu"]) {
  test(`the page's own words are said in ${language}`, async ({
    page: target,
  }) => {
    await seedLayout(target);
    await open(target, "signed-in", `&lang=${language}`);
    await openRailView(target, "desktop.withholding.title", language);
    const page = withholdingPage(target);
    await expect(page).toBeVisible();
    await expect(
      page.getByRole("heading", {
        name: label("desktop.withholding.records.title", {}, language),
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", {
        name: label("desktop.withholding.absences.title", {}, language),
      }),
    ).toBeVisible();
    await expect(
      page.getByLabel(label("desktop.withholding.ejercicio", {}, language), {
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: label("desktop.withholding.change", {}, language),
      }),
    ).toBeVisible();
  });
}
