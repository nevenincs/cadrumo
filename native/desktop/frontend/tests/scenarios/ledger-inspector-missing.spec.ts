import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { servedPeriodName } from "../support/servedPeriods";
import { fixtureYear } from "../../src/dev/fixtureDates";

// What the inspector's Classify section lists as still missing, over the
// scenario's ledger: every item opens the editor of exactly that fact, the
// IVA figures can be worked out from the movement's IVA category as a staged
// proposal, and a fact that cannot change says why instead of answering a
// press with nothing.

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const panel = (target: Page) => target.locator("aside.ledger-panel");
const body = (target: Page) => panel(target).locator(".ledger-inspector-body");
const tray = (target: Page) => target.locator(".ledger-tray");
const search = (target: Page) =>
  page(target).getByRole("searchbox", {
    name: label("desktop.ledger.search.label"),
  });

async function openLedger(target: Page) {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(dataRows(target).first()).toBeVisible();
}

async function choosePeriod(target: Page, year: number, code: string) {
  await target.locator('[data-dock-pane="docs"] .ledger-period').click();
  const periods = target.getByRole("dialog", {
    name: label("desktop.ledger.period.choose"),
  });
  const shown = periods.locator("[aria-live=polite]");
  for (let guard = 0; guard < 40; guard += 1) {
    const at = Number(await shown.textContent());
    if (at === year) break;
    await periods
      .getByRole("button", {
        name: label(
          at > year
            ? "desktop.ledger.period.year_previous"
            : "desktop.ledger.period.year_next",
        ),
        exact: true,
      })
      .click();
  }
  await periods
    .getByRole("group", {
      name: label("desktop.ledger.period.of_year", { year }),
    })
    .getByRole("button", {
      name: servedPeriodName(year, code),
      exact: true,
    })
    .click();
  await expect(periods).toBeHidden();
  await expect(dataRows(target).first()).toBeVisible();
}

/** Finds the movement by search, as the grid draws only the rows in view,
 * then selects it and opens the inspector on it with Alt+I. */
async function inspect(target: Page, text: string) {
  await search(target).fill(text);
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
}

/** How many changes the tray counts: none where there is no tray. */
const trayCount = async (target: Page) =>
  (await tray(target).count())
    ? Number(
        await tray(target)
          .locator(".ledger-tray-toggle span[aria-hidden=true]")
          .textContent(),
      )
    : 0;

/** Chooses `option` in the combobox the focused trigger opened. */
async function choose(target: Page, option: string) {
  const list = target.locator("[data-slot=combobox]");
  await expect(list).toBeVisible();
  await target.keyboard.type(option);
  await list.getByRole("option", { name: option }).first().click();
  await expect(list).toHaveCount(0);
}

/** The movement whose invoice figures were never entered: base, rate and
 * cuota are all missing though it carries an IVA category. */
const UNFIGURED = "ESTUDIO GARCIA ASESORES";

/** The missing IVA facts the check reports, with the field each is put right
 * in, in the order the ledger names them. */
const MISSING_IVA_FACTS = [
  ["missing_taxable_base", "taxable_base"],
  ["missing_iva_amount", "iva_amount"],
  ["missing_iva_rate", "iva_rate"],
] as const;

const missingItem = (target: Page, reason: string) =>
  body(target)
    .locator(".ledger-missing li")
    .filter({ hasText: label(`desktop.ledger.reason_detail.${reason}`) });

const toast = (target: Page) =>
  panel(target).locator(".ledger-inspector-toast");

test("each missing IVA fact opens the editor of exactly that fact", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, fixtureYear, "3T");
  await inspect(target, UNFIGURED);
  await expect(body(target).locator(".ledger-missing li")).toHaveCount(
    MISSING_IVA_FACTS.length,
  );
  // The list says why the facts are wanted, and that nothing is saved yet.
  await expect(body(target).locator(".ledger-missing")).toContainText(
    label("desktop.ledger.inspector.missing_why"),
  );
  for (const [reason, field] of MISSING_IVA_FACTS) {
    await missingItem(target, reason)
      .getByRole("button", { name: label("desktop.ledger.inspector.fix.go") })
      .click();
    const typing = body(target).locator("input:focus");
    await expect(typing).toBeVisible();
    await expect(typing).toHaveAccessibleName(
      label(`desktop.ledger.column.${field}`),
    );
    // Leaving the editor unchanged stages nothing.
    await target.keyboard.press("Escape");
    await expect(typing).toHaveCount(0);
    await expect(body(target).locator(`[data-field=${field}]`)).toBeFocused();
  }
  expect(await trayCount(target)).toBe(0);
});

test("a missing IVA fact is worked out from the IVA category as a staged proposal, never filled in", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, fixtureYear, "3T");
  await inspect(target, UNFIGURED);
  const derive = body(target)
    .locator(".ledger-missing")
    .getByRole("button", {
      name: label("desktop.ledger.inspector.fix.derive_from_category"),
    });
  // One button for the three facts, not one for each.
  await expect(derive).toHaveCount(1);
  await derive.click();
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.inspector.derive.staged_toast"),
  );
  await expect(body(target).locator(".ledger-derive")).toContainText(
    label("desktop.ledger.inspector.derive.staged", {
      category: label("desktop.ledger.iva_category.domestic_general"),
    }),
  );
  expect(await trayCount(target)).toBe(1);
  // Asked again, it says the proposal is already waiting and stages no more.
  await derive.click();
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.inspector.fix.derive_already"),
  );
  expect(await trayCount(target)).toBe(1);
});

test("working a missing fact out needs the IVA category: without one the list opens and says so", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, fixtureYear, "3T");
  await inspect(target, UNFIGURED);
  await body(target).locator("[data-field=iva_category]").click();
  await choose(target, label("desktop.ledger.inspector.clear"));
  await body(target)
    .locator(".ledger-missing")
    .getByRole("button", {
      name: label("desktop.ledger.inspector.fix.derive_from_category"),
    })
    .click();
  await expect(target.locator("[data-slot=combobox]")).toBeVisible();
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.inspector.fix.derive_needs_category"),
  );
  await target.keyboard.press("Escape");
  // Nothing was derived: the only staged change is the cleared category.
  await expect(
    body(target)
      .locator(".ledger-derive")
      .getByRole("button", {
        name: label("desktop.ledger.inspector.derive.stage"),
      }),
  ).toBeVisible();
  expect(await trayCount(target)).toBe(1);
});

test("a fix button on a movement a declaration uses says why it cannot change, never nothing", async ({
  page: target,
}) => {
  await openLedger(target);
  await choosePeriod(target, fixtureYear, "1T");
  await inspect(target, "FIBRA HOGAR ALBOR");
  const fixes = body(target)
    .locator(".ledger-missing li")
    .getByRole("button", { name: label("desktop.ledger.inspector.fix.go") });
  await expect(fixes.first()).toBeVisible();
  // Never disabled: a disabled control would say nothing.
  await expect(fixes.first()).toBeEnabled();
  await fixes.first().click();
  await expect(toast(target)).toContainText(
    label("desktop.ledger.edit.lock.sealed"),
  );
  await expect(body(target).locator("input:focus")).toHaveCount(0);
});
