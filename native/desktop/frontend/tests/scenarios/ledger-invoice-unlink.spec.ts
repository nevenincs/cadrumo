import { expect, test, type Page } from "@playwright/test";
import { captureUnrecordedQuestions } from "../support/stagedCheckCapture";
import { label } from "../support/strings";
import { servedPeriodName } from "../support/servedPeriods";
import { fixtureYear } from "../../src/dev/fixtureDates";
import { fixtureLedger } from "../../src/dev/fixtures/ledger";

// A saved link between a movement and an invoice is removed from the
// movement's Invoice section: the removal is staged with the movement and
// the invoice as shown, the review names both sides, and the save clears the
// link and records it in the movement's history. A movement a finalized
// declaration cites keeps its link, and the review says why and what to do.

async function openLedger(target: Page) {
  await captureUnrecordedQuestions(target);
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(dataRows(target).first()).toBeVisible();
}

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const panel = (target: Page) => target.locator("aside.ledger-panel");
const index = (target: Page) => panel(target).locator(".ledger-jump-index");
const body = (target: Page) => panel(target).locator(".ledger-inspector-body");
const tray = (target: Page) => target.locator(".ledger-tray");
const review = (target: Page) => target.locator(".ledger-review");
const invoiceSection = (target: Page) =>
  body(target).locator("[data-section-body=invoice]");

const rowOf = (target: Page, text: string) =>
  dataRows(target)
    .filter({
      has: target.locator("[data-column=description]", { hasText: text }),
    })
    .first();

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
    .getByRole("button", { name: servedPeriodName(year, code), exact: true })
    .click();
  await expect(periods).toBeHidden();
  await expect(dataRows(target).first()).toBeVisible();
}

async function inspect(target: Page, text: string) {
  await rowOf(target, text).locator("[data-column=status]").click();
  if (!(await panel(target).isVisible()))
    await target.keyboard.press("Alt+KeyI");
  await expect(panel(target).locator(".ledger-inspector h2")).toContainText(
    text,
  );
}

async function jumpTo(target: Page, section: string, name: string) {
  const entry = index(target).locator(`[data-section=${section}]`);
  if (await entry.count()) await entry.click();
  else {
    await index(target).locator(".ledger-jump-more").click();
    await target.getByRole("menuitem", { name, exact: true }).click();
  }
  await expect(body(target).locator(`#inspector-${section}`)).toBeFocused();
}

async function openReview(target: Page) {
  await tray(target).locator(".ledger-tray-review").click();
  await expect(review(target)).toBeVisible();
  await expect(review(target).locator(".ledger-review-summary")).not.toHaveText(
    label("desktop.ledger.apply.reading"),
  );
}

async function save(target: Page) {
  await review(target).locator(".ledger-apply-save").click();
  await expect(review(target).locator(".ledger-apply-done")).toBeVisible({
    timeout: 20_000,
  });
}

/** A client transfer the scenario links to its issued invoice, in a month a
 * finalized declaration seals or in one it does not. */
function linkedTransfer(sealed: boolean) {
  const ledger = fixtureLedger();
  const movement = ledger.movements.find(
    (found) =>
      found.sealed === sealed &&
      found.transaction.invoice_id !== null &&
      found.transaction.description.startsWith("TRANSFERENCIA "),
  )!;
  const invoice = ledger.invoices.find(
    (found) => found.invoice_id === movement.transaction.invoice_id,
  )!;
  return {
    description: movement.transaction.description,
    number: invoice.invoice_number,
    // The quarter of the movement's day, as the period chooser names it.
    quarter: `${Math.ceil(Number(movement.transaction.date.slice(5, 7)) / 3)}T`,
  };
}

/** Stages the removal of the inspected movement's link from its Invoice
 * section, and returns the section. */
async function stageUnlink(target: Page, number: string) {
  await jumpTo(
    target,
    "invoice",
    label("desktop.ledger.inspector.section.invoice"),
  );
  const section = invoiceSection(target);
  await expect(section.locator(".ledger-linked-invoice")).toContainText(number);
  await section
    .getByRole("button", {
      name: label("desktop.ledger.inspector.invoice.unlink"),
    })
    .click();
  await expect(section.locator(".ledger-invoice-unlinking")).toContainText(
    label("desktop.ledger.inspector.invoice.unlink_pending", {
      invoice: number,
    }),
  );
  return section;
}

test("a saved link is removed from the movement's Invoice section, named in the review with both sides, and kept in the history", async ({
  page: target,
}) => {
  const transfer = linkedTransfer(false);
  await openLedger(target);
  await choosePeriod(target, fixtureYear, transfer.quarter);
  await inspect(target, transfer.description);
  const section = await stageUnlink(target, transfer.number);
  // Staged, not saved: the link is still drawn, and it can be dropped.
  await expect(
    section.getByRole("button", {
      name: label("desktop.ledger.inspector.invoice.unlink"),
    }),
  ).toHaveCount(0);
  await openReview(target);
  const links = review(target).locator(".ledger-links");
  await expect(links).toContainText(label("desktop.ledger.apply.links_note"));
  const removal = links.locator("[data-unlink]");
  await expect(removal).toHaveCount(1);
  await expect(removal).toContainText(
    label("desktop.ledger.apply.action.unlink"),
  );
  await expect(removal).toContainText(transfer.number);
  // A removal asks for no tick: the save is open at once.
  await expect(
    review(target).locator(".ledger-apply-save"),
  ).not.toHaveAttribute("aria-disabled", "true");
  await save(target);
  await expect(review(target).locator("[data-outcome=refused]")).toHaveCount(0);
  await review(target).locator(".ledger-apply-done").click();
  await expect(review(target)).toBeHidden();
  // The movement is read again with no invoice, and offers a link instead.
  await expect(section.locator(".ledger-linked-invoice")).toHaveCount(0);
  await expect(section.locator(".ledger-invoice-unlinking")).toHaveCount(0);
  await expect(section).toContainText(
    label("desktop.ledger.inspector.invoice.removable"),
  );
  await jumpTo(
    target,
    "history",
    label("desktop.ledger.inspector.section.history"),
  );
  await expect(body(target).locator(".ledger-history")).toContainText(
    label("desktop.ledger.inspector.event.unlinked"),
  );
});

test("a link a finalized declaration seals is refused with its cause and the next step, and stays staged", async ({
  page: target,
}) => {
  const transfer = linkedTransfer(true);
  await openLedger(target);
  await choosePeriod(target, fixtureYear, transfer.quarter);
  await inspect(target, transfer.description);
  const section = await stageUnlink(target, transfer.number);
  await openReview(target);
  await save(target);
  const refused = review(target).locator("[data-outcome=refused]");
  await expect(refused).toHaveCount(1);
  await expect(refused).toContainText(
    label(
      "desktop.ledger.inspector.invoice.unlink_cause.finalized_calculation_reference",
    ),
  );
  await expect(refused).toContainText(
    label(
      "desktop.ledger.inspector.invoice.unlink_next_step.reopen_finalized_calculation",
    ),
  );
  await review(target).locator(".ledger-apply-done").click();
  await expect(review(target)).toBeHidden();
  // The link is still there, and so is its staged removal, to drop.
  await expect(section.locator(".ledger-linked-invoice")).toContainText(
    transfer.number,
  );
  const pending = section.locator(".ledger-invoice-unlinking");
  await expect(pending).toBeVisible();
  await pending
    .getByRole("button", { name: label("desktop.ledger.inspector.drop") })
    .click();
  await expect(pending).toHaveCount(0);
  await expect(
    section.getByRole("button", {
      name: label("desktop.ledger.inspector.invoice.unlink"),
    }),
  ).toBeVisible();
});
