import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

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
async function inspectMovement(target: Page) {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  const grid = target.locator(".ledger-page").getByRole("grid");
  await expect(grid).toBeVisible();
  const row = grid
    .locator("[data-kind=data]")
    .filter({
      has: target.locator("[data-column=description]", { hasText: MOVEMENT }),
    })
    .first();
  await row.locator("[data-column=status]").click();
  if (!(await panel(target).isVisible()))
    await target.keyboard.press("Alt+KeyI");
  await expect(panel(target).locator(".ledger-inspector h2")).toContainText(
    MOVEMENT,
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

test("the notes offer no suggestions", async ({ page: target }) => {
  await inspectMovement(target);
  await field(target, "notes").click();
  const input = body(target).locator("input:focus");
  await input.fill("a");
  await expect(input).not.toHaveAttribute("role", "combobox");
  await expect(target.getByRole("listbox")).toHaveCount(0);
});
