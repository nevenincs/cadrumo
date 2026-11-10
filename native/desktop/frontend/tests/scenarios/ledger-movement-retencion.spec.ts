import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { servedPeriodName } from "../support/servedPeriods";
import { LEDGER_FIXTURE_TODAY } from "../../src/dev/fixtures/ledger";

/** The year of the scenario ledger's date, whose periods the scenarios open. */
const scenarioYear = Number(LEDGER_FIXTURE_TODAY.slice(0, 4));

// The Movements grid shows the retención a received invoice leaves on the
// payment that settles it, as the product serves it: the 318.00 payment of a
// professional's fee shows the 45.00 withheld, and a payment of no invoice
// that states a retención shows an empty cell, never a zero.

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const rowOf = (target: Page, text: string) =>
  dataRows(target).filter({
    has: target.locator("[data-column=description]", { hasText: text }),
  });

async function openLedger(target: Page) {
  await target.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&ledger=withholding",
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
}

async function chooseWholeYear(target: Page) {
  await target
    .locator(".pane-docs .pane-head")
    .locator(".ledger-period")
    .click();
  const periods = target.getByRole("dialog", {
    name: label("desktop.ledger.period.choose"),
  });
  const shown = periods.locator("[aria-live=polite]");
  for (let guard = 0; guard < 40; guard += 1) {
    const at = Number(await shown.textContent());
    if (at === scenarioYear) break;
    await periods
      .getByRole("button", {
        name: label(
          at > scenarioYear
            ? "desktop.ledger.period.year_previous"
            : "desktop.ledger.period.year_next",
        ),
        exact: true,
      })
      .click();
  }
  await periods
    .getByRole("group", {
      name: label("desktop.ledger.period.of_year", { year: scenarioYear }),
    })
    .getByRole("button", {
      name: servedPeriodName(scenarioYear, "0A"),
      exact: true,
    })
    .click();
  await expect(periods).toBeHidden();
}

test("the 318.00 payment of a professional's invoice lists the 45.00 retención withheld on it", async ({
  page: target,
}) => {
  await openLedger(target);
  await chooseWholeYear(target);
  await expect(
    grid(target).getByRole("columnheader", {
      name: label("desktop.ledger.column.retencion"),
      exact: true,
    }),
  ).toHaveCount(1);
  const payment = rowOf(target, "PEDRO GESTOR EJEMPLO");
  await expect(payment).toHaveCount(1);
  await expect(payment.locator("[data-column=amount]")).toContainText("318.00");
  const cell = payment.locator("[data-column=retencion] [data-retencion]");
  await expect(cell).toHaveText("45.00");
  await expect(cell).toHaveAttribute("data-retencion", "practised");
  // Its tooltip names the invoice and the modelo the retención is declared on.
  await expect(cell).toHaveAttribute(
    "title",
    label("desktop.ledger.retencion.practised", {
      invoice: `${scenarioYear}-GES-001`,
      modelo: "111",
    }),
  );
});

test("a payment of no invoice that states a retención shows an empty retención cell", async ({
  page: target,
}) => {
  await openLedger(target);
  await chooseWholeYear(target);
  const payment = rowOf(target, "ESTUDIO GARCIA ASESORES");
  await expect(payment).toHaveCount(1);
  await expect(payment.locator("[data-column=retencion]")).toBeEmpty();
});
