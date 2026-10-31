import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { profileInput } from "../../src/shell/profileInput";
import type { UserProfile } from "../../src/shell/userProfile";
import { label } from "../support/strings";

// Suggestions in the Ledger's Setup panes over the scenario's ledger, and the
// browser hints on the profile and on secret fields: a pick writes the field
// and runs what the pane runs on its own value, a masked secret is offered
// nothing and asks the browser to keep nothing, and every profile detail asks
// it to remember nothing.

const head = (target: Page) => target.locator(".pane-docs .pane-head");
// The open list takes the field's name, so the control is told from it.
const field = (scope: Page | Locator, key: string) =>
  scope
    .getByLabel(label(key), { exact: true })
    .and(scope.locator("input, select, textarea"));
const options = (target: Page) =>
  target.getByRole("listbox").getByRole("option");

async function openSetup(
  target: Page,
  section: "rules" | "registers",
  area: string,
) {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-page").getByRole("grid")).toBeVisible();
  await head(target).locator(".ledger-setup").click();
  await target
    .getByRole("menuitem", { name: label(`desktop.ledger.section.${section}`) })
    .click();
  await expect(target.locator(`.ledger-setup-${section}`)).toBeVisible();
  await expect(target.getByRole("menu")).toHaveCount(0);
  await target.getByRole("tab", { name: label(area), exact: true }).click();
}

test("a tax id picked from the invoices looks the counterparty up", async ({
  page: target,
}) => {
  await openSetup(target, "rules", "desktop.ledger.rules.area.counterparties");
  const taxId = field(target, "desktop.ledger.counterparty.tax_id");
  await taxId.fill("B000000");
  await expect(options(target).first()).toBeVisible();
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Enter");
  await expect(taxId).toHaveValue(/^B000000\d\d$/);
  // No press on the view button: the pick asked.
  await expect(target.locator(".ledger-counterparty-answer")).toBeVisible();
  expect(
    await target.evaluate(() =>
      [localStorage, sessionStorage].flatMap((store) =>
        Object.keys(store).filter((key) =>
          (store.getItem(key) ?? "").includes("B000000"),
        ),
      ),
    ),
  ).toEqual([]);
});

test("Escape closes the tax id list and looks nothing up", async ({
  page: target,
}) => {
  await openSetup(target, "rules", "desktop.ledger.rules.area.counterparties");
  const taxId = field(target, "desktop.ledger.counterparty.tax_id");
  await taxId.fill("B000000");
  await expect(options(target).first()).toBeVisible();
  await taxId.press("Escape");
  await expect(options(target)).toHaveCount(0);
  // The list closed alone: nothing was picked and nothing was looked up.
  await expect(taxId).toHaveValue("B000000");
  await expect(target.locator(".ledger-counterparty-answer")).toHaveCount(0);
});

test("a prorrata reference is offered from the register's earlier ones", async ({
  page: target,
}) => {
  await openSetup(
    target,
    "registers",
    "desktop.ledger.registers.area.prorrata",
  );
  await target
    .getByRole("button", {
      name: label("desktop.ledger.prorrata.action.elect_especial"),
    })
    .click();
  const reference = field(
    target.locator(".ledger-prorrata-form"),
    "desktop.ledger.prorrata.reference",
  );
  await reference.fill("REF-");
  await expect(options(target)).toHaveText("REF-2025-0042");
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Enter");
  await expect(reference).toHaveValue("REF-2025-0042");
  await expect(reference).toBeFocused();
});

test("an account's bank block and number are offered nothing and keep out of browser history", async ({
  page: target,
}) => {
  await openSetup(
    target,
    "registers",
    "desktop.ledger.registers.area.accounts",
  );
  await target
    .getByRole("button", { name: label("desktop.ledger.accounts.add") })
    .first()
    .click();
  const form = target.locator(".ledger-account-form");
  for (const key of [
    "iban",
    "swift_bic",
    "bank_name",
    "bank_address",
    "bank_city",
    "bank_country",
  ]) {
    const secret = field(form, `desktop.ledger.accounts.${key}`);
    await expect(secret).toHaveAttribute("type", "password");
    await expect(secret).toHaveAttribute("autocomplete", "new-password");
    await expect(secret).not.toHaveAttribute("role", "combobox");
  }
  // The currency is a plain code field that offers the codes in use.
  const currency = field(form, "desktop.ledger.accounts.currency");
  await expect(currency).toHaveAttribute("autocomplete", "off");
  await currency.fill("E");
  await expect(options(target).filter({ hasText: "EUR" })).toBeVisible();
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Enter");
  await expect(currency).toHaveValue("EUR");
});

test("every profile detail asks the browser to remember nothing", async () => {
  const { en } = JSON.parse(
    readFileSync(
      fileURLToPath(
        new URL("../../src/dev/fixtures/userProfile.json", import.meta.url),
      ),
      "utf8",
    ),
  ) as { en: UserProfile };
  const details = en.sections.flatMap((section) => section.fields);
  expect(details.length).toBeGreaterThan(20);
  for (const detail of details) {
    const input = profileInput(detail);
    expect(input.autoComplete, detail.path).toBe("off");
    expect(input.type === "tel", detail.path).toBe(
      detail.path === "contact.contact_person_phone",
    );
  }
});
