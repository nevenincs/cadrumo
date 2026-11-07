import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { fixtureYear } from "../../src/dev/fixtureDates";

// Suggestions in the movement inspector over the scenario's ledger: picking a
// counterparty stages the country and identification state the movement left
// empty, leaves one the person typed, and the list never reaches the notes.

const MOVEMENT = "COMISION MANTENIMIENTO CUENTA";
const PARTY = "SoftNube Ireland Ltd";

const panel = (target: Page) => target.locator("aside.ledger-panel");
const body = (target: Page) => panel(target).locator(".ledger-inspector-body");
// The country is also entered under the Classify section's other tax facts.
const field = (target: Page, name: string) =>
  body(target)
    .getByRole("region", {
      name: label("desktop.ledger.inspector.section.details"),
    })
    .locator(`[data-field=${name}]`);

/** Opens the inspector on the movement, which names no counterparty. */
async function inspectMovement(target: Page, movement = MOVEMENT) {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  const grid = target.locator(".ledger-page").getByRole("grid");
  await expect(grid).toBeVisible();
  const row = grid
    .locator("[data-kind=data]")
    .filter({
      has: target.locator("[data-column=description]", { hasText: movement }),
    })
    .first();
  await row.locator("[data-column=status]").click();
  if (!(await panel(target).isVisible()))
    await target.keyboard.press("Alt+KeyI");
  await expect(panel(target).locator(".ledger-inspector h2")).toContainText(
    movement,
  );
}

/** Types the start of the party in the counterparty field and chooses it. */
async function pickParty(target: Page) {
  await field(target, "counterparty").click();
  const input = body(target).locator("input:focus");
  await input.fill("SoftNube");
  await expect(
    target.getByRole("option").filter({ hasText: PARTY }),
  ).toBeVisible();
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Enter");
  await expect(input).toHaveValue(PARTY);
}

test("a pick in the counterparty stages the empty country and state", async ({
  page: target,
}) => {
  await inspectMovement(target);
  await expect(field(target, "counterparty_country")).not.toContainText("IE");
  await expect(target.locator(".ledger-tray")).toHaveCount(0);
  await pickParty(target);
  await expect(field(target, "counterparty_country")).toContainText("IE");
  await expect(
    field(target, "counterparty_identification_state"),
  ).toContainText("IE");
  await expect(target.locator(".ledger-tray")).toBeVisible();
});

test("the country field offers the served codes, by name, and still takes another", async ({
  page: target,
}) => {
  await inspectMovement(target);
  await field(target, "counterparty_country").click();
  const input = body(target).locator("input:focus");
  await input.fill("Port");
  const offered = target.getByRole("option").filter({ hasText: "PT" });
  await expect(offered).toBeVisible();
  await expect(offered).toContainText("Portugal");
  // A real code the list does not hold is still recordable.
  await input.fill("MC");
  await target.keyboard.press("Enter");
  await expect(field(target, "counterparty_country")).toContainText("MC");
});

test("the deduction kind is a closed, worded choice", async ({
  page: target,
}) => {
  await inspectMovement(target);
  const more = body(target).locator(".ledger-more-tax");
  await more.locator("summary").click();
  await more.locator("[data-field=deduction_fact_kind]").click();
  await target
    .getByRole("option", {
      name: label(
        "application.ledger.entry_options.deduction_fact_kind.rectification",
      ),
    })
    .click();
  await expect(more.locator("[data-field=deduction_fact_kind]")).toContainText(
    label("application.ledger.entry_options.deduction_fact_kind.rectification"),
  );
});

test("the Modelo 210 income type is a closed, worded choice", async ({
  page: target,
}) => {
  await inspectMovement(target, "TRANSFERENCIA");
  const more = body(target).locator(".ledger-more-tax");
  await more.locator("summary").click();
  await more
    .getByRole("button", {
      name: label("desktop.ledger.inspector.m210.tipo_renta_code"),
    })
    .click();
  const code = target.getByRole("option", {
    name: `24 · ${label("application.ledger.entry_options.m210_income_concept.general")}`,
  });
  await expect(code).toBeVisible();
  await code.click();
  await expect(more).toContainText(
    `24 · ${label("application.ledger.entry_options.m210_income_concept.general")}`,
  );
});

test("a pick in the counterparty leaves a country already typed", async ({
  page: target,
}) => {
  await inspectMovement(target);
  await field(target, "counterparty_country").click();
  await body(target).locator("input:focus").fill("FR");
  await target.keyboard.press("Enter");
  await expect(field(target, "counterparty_country")).toContainText("FR");
  await pickParty(target);
  await expect(field(target, "counterparty_country")).toContainText("FR");
  await expect(field(target, "counterparty_country")).not.toContainText("IE");
  await expect(
    field(target, "counterparty_identification_state"),
  ).toContainText("IE");
});

test("a counterparty reaches past the rows on screen", async ({
  page: target,
}) => {
  await inspectMovement(target);
  await field(target, "counterparty").click();
  await body(target).locator("input:focus").fill("Asesor");
  await expect(
    target.getByRole("option").filter({ hasText: "Asesoría Antigua, S.L." }),
  ).toBeVisible();
});

test("a description reaches past the rows on screen", async ({
  page: target,
}) => {
  await inspectMovement(target);
  await field(target, "description").click();
  await body(target).locator("input:focus").fill("colegio");
  await expect(
    target
      .getByRole("option")
      .filter({ hasText: "Cuota del colegio profesional" }),
  ).toBeVisible();
});

test("a group label typed is offered again before it is saved", async ({
  page: target,
}) => {
  await inspectMovement(target);
  await field(target, "group_label").click();
  await body(target).locator("input:focus").fill("Etiqueta nueva");
  await target.keyboard.press("Enter");
  await expect(field(target, "group_label")).toContainText("Etiqueta nueva");
  await field(target, "group_label").click();
  await body(target).locator("input:focus").fill("Etiq");
  await expect(
    target.getByRole("option").filter({ hasText: "Etiqueta nueva" }),
  ).toBeVisible();
});

test("a prorrata is offered by what the register says of it, and names its reference", async ({
  page: target,
}) => {
  await inspectMovement(target);
  await body(target).locator(".ledger-more-tax summary").click();
  const prorrata = body(target).getByLabel(
    label("desktop.ledger.inspector.allocate.prorrata"),
    { exact: true },
  );
  await prorrata.scrollIntoViewIfNeeded();
  await prorrata.click();
  const entry = target
    .getByRole("option")
    .filter({ hasText: String(fixtureYear - 1) })
    .first();
  await expect(entry).toBeVisible();
  await expect(entry).toContainText(
    label("desktop.ledger.prorrata.kind.definitiva"),
  );
  await expect(entry).toContainText(
    label("desktop.ledger.prorrata.regime.general"),
  );
  await entry.click();
  await expect(prorrata).toHaveValue(
    `prorrata:${fixtureYear - 1}:definitiva:general`,
  );
  await expect(prorrata).not.toHaveAttribute("maxlength");
});

test("an investment asset is offered from the capital goods register", async ({
  page: target,
}) => {
  await inspectMovement(target);
  await body(target).locator(".ledger-more-tax summary").click();
  const asset = body(target).locator("[data-field=investment_asset_id]");
  await asset.click();
  await body(target).locator("input:focus").fill("BI");
  await expect(target.getByRole("option").first()).toBeVisible();
});

test("the notes offer no suggestions", async ({ page: target }) => {
  await inspectMovement(target);
  await field(target, "notes").click();
  const input = body(target).locator("input:focus");
  await input.fill("a");
  await expect(input).not.toHaveAttribute("role", "combobox");
  await expect(target.getByRole("listbox")).toHaveCount(0);
});
