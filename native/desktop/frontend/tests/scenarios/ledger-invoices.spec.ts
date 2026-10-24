import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { label } from "../support/strings";

// The Invoices section over the scenario's ledger: the whole catalogue,
// filtered and sorted in the page, and the invoice editor. A new invoice
// starts with nothing assumed, names its four requirements, works its lines,
// totals and retención out, and suggests the next number of its series; a
// stored one shows its identity as fixed and corrects only what the ledger
// accepts. Writes are reviewed first, an unseen outcome is said to be
// unknown, and leaving with edits asks first.

const open = (target: Page, extra = "") =>
  target.goto(`/scenarios.html?scenario=ledger&latency=0&bar=off${extra}`);

const section = (target: Page) => target.locator(".ledger-invoices");
const grid = (target: Page) => section(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const editor = (target: Page) => target.locator(".ledger-invoice-editor");
const toast = (target: Page) => section(target).locator(".ledger-toast");
const field = (target: Page, key: string) =>
  editor(target).getByLabel(label(`desktop.ledger.invoices.field.${key}`), {
    exact: true,
  });
const lineCell = (target: Page, line: number, cell: number) =>
  editor(target)
    .locator(".ledger-invoice-lines tbody tr")
    .nth(line)
    .locator("td")
    .nth(cell)
    .locator("input, select");

async function openInvoices(target: Page, extra = "") {
  await open(target, extra);
  await target.locator("[data-rail=ledger]").click();
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.invoices") })
    .click();
  await expect(grid(target)).toBeVisible();
}

async function allPeriods(target: Page) {
  await target.locator(".pane-docs .pane-head .ledger-period").click();
  await target.locator(".ledger-period-all").click();
}

async function counted(
  target: Page,
): Promise<{ shown: number; total: number }> {
  const count = section(target).locator(".ledger-invoices-count");
  return {
    shown: Number(await count.getAttribute("data-shown")),
    total: Number(await count.getAttribute("data-total")),
  };
}

/** The text of each shown row's number cell. */
async function numbers(target: Page): Promise<string[]> {
  return dataRows(target).locator(".ledger-invoice-number").allTextContents();
}

async function openStored(target: Page, number: string) {
  await dataRows(target).filter({ hasText: number }).first().dblclick();
  await expect(editor(target)).toBeVisible();
}

async function addNew(target: Page) {
  await target.locator(".pane-docs .pane-head .ledger-add").click();
  await expect(editor(target)).toBeVisible();
}

/** Fills an issued invoice to Norte Digital with two lines at 21%. */
async function fillIssued(target: Page, number = "F-2026-021") {
  await editor(target)
    .getByRole("radio", {
      name: label("desktop.ledger.invoices.kind_choice.issued"),
    })
    .click();
  await field(target, "counterparty_name").fill("Norte Digital S. Coop.");
  await field(target, "counterparty_tax_id").fill("F00000022");
  await field(target, "counterparty_country").fill("es");
  await field(target, "series").fill("F");
  await field(target, "invoice_number").fill(number);
  await field(target, "issued_at").fill("2026-10-23");
  await field(target, "currency").fill("eur");
  await lineCell(target, 0, 0).fill("Diseño de marca");
  await lineCell(target, 0, 2).fill("550");
  await lineCell(target, 0, 4).selectOption("RATE_21");
  await editor(target)
    .getByRole("button", { name: label("desktop.ledger.invoices.line.add") })
    .click();
  await lineCell(target, 1, 0).fill("Piezas gráficas");
  await lineCell(target, 1, 1).fill("2");
  await lineCell(target, 1, 2).fill("275");
  await lineCell(target, 1, 4).selectOption("RATE_21");
}

const button = (
  target: Page,
  key: string,
  values?: Record<string, string | number>,
) =>
  editor(target).getByRole("button", { name: label(key, values), exact: true });

test("the catalogue filters by kind, class, payment, links and words, and sorts", async ({
  page: target,
}) => {
  await openInvoices(target);
  await allPeriods(target);
  await expect
    .poll(async () => (await counted(target)).total)
    .toBeGreaterThan(40);
  const { total } = await counted(target);
  expect((await counted(target)).shown).toBe(total);

  await section(target)
    .getByRole("radio", {
      name: label("desktop.ledger.invoices.kinds.received"),
    })
    .click();
  const received = (await counted(target)).shown;
  expect(received).toBeGreaterThan(0);
  expect(received).toBeLessThan(total);
  await section(target)
    .getByRole("radio", { name: label("desktop.ledger.invoices.kinds.all") })
    .click();

  await section(target)
    .locator(".ledger-invoices-class")
    .selectOption("RECTIFICATIVA");
  await expect.poll(() => numbers(target)).toEqual(["R-2026-02"]);
  await section(target).locator(".ledger-invoices-class").selectOption("");

  await section(target)
    .locator(".ledger-invoices-payment")
    .selectOption("OVERDUE");
  await expect.poll(() => numbers(target)).toEqual(["F-2026-020"]);
  await section(target).locator(".ledger-invoices-payment").selectOption("");

  const unmatched = section(target).locator(".ledger-invoices-unmatched");
  await unmatched.click();
  await expect(unmatched).toHaveAttribute("aria-pressed", "true");
  // The invoices no movement settles are the seven examples.
  await expect.poll(async () => (await counted(target)).shown).toBe(7);
  await unmatched.click();

  // Words match separately, accents aside, and a figure written either way.
  await section(target)
    .locator(".ledger-invoices-search")
    .fill("papeleria 93,17");
  await expect.poll(() => numbers(target)).toEqual(["A-1093"]);
  await section(target).locator(".ledger-invoices-search").fill("");

  // Sorting by total, client side, over the whole catalogue.
  const totalHeader = grid(target).getByRole("columnheader", {
    name: label("desktop.ledger.invoices.column.total"),
  });
  await totalHeader.click();
  await expect(totalHeader).toHaveAttribute("aria-sort", "ascending");
  await expect.poll(async () => (await numbers(target))[0]).toBe("T-2026-0007");
  await totalHeader.click();
  await expect(totalHeader).toHaveAttribute("aria-sort", "descending");
});

test("a new invoice assumes no kind, country or currency", async ({
  page: target,
}) => {
  await openInvoices(target);
  await addNew(target);
  const kinds = editor(target).getByRole("radio");
  await expect(kinds).toHaveCount(2);
  for (const kind of await kinds.all())
    await expect(kind).toHaveAttribute("aria-checked", "false");
  // The editor opens on its first field.
  await expect(kinds.first()).toBeFocused();
  await expect(field(target, "counterparty_country")).toHaveValue("");
  await expect(field(target, "currency")).toHaveValue("");
  await expect(lineCell(target, 0, 4)).toHaveValue("");
  await expect(
    editor(target).locator("[data-invariant][data-met]"),
  ).toHaveCount(0);
});

test("an issued invoice with two lines at 21% and a 15% retención is added", async ({
  page: target,
}) => {
  await openInvoices(target);
  await allPeriods(target);
  const before = (await counted(target)).total;
  await addNew(target);
  await fillIssued(target);
  await expect(
    editor(target).locator("[data-invariant][data-met]"),
  ).toHaveCount(4);
  await expect(editor(target).locator(".ledger-invoice-total")).toContainText(
    "1,331.00",
  );
  // The retención is worked out from the rate.
  await editor(target)
    .getByRole("button", { name: "15%", exact: true })
    .click();
  await expect(field(target, "retention_amount")).toHaveValue("165");
  await expect(editor(target).locator(".ledger-invoice-to-pay")).toHaveText(
    label("desktop.ledger.invoices.to_pay_withheld", {
      amount: "1,166.00",
      retention: "165.00",
    }),
  );
  await button(target, "desktop.ledger.invoices.review").click();
  await expect(editor(target).locator(".ledger-invoice-confirm")).toBeVisible();
  await button(target, "desktop.ledger.invoices.add").click();
  await expect(editor(target)).toBeHidden();
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.invoices.added", { number: "F-2026-021" }),
  );
  await expect.poll(async () => (await counted(target)).total).toBe(before + 1);
  await openStored(target, "F-2026-021");
  await expect(
    editor(target).locator(".ledger-invoice-lines tbody tr"),
  ).toHaveCount(2);
  await expect(field(target, "retention_amount")).toHaveValue("165");
});

test("each requirement and rule is refused on its own field", async ({
  page: target,
}) => {
  await openInvoices(target);
  await addNew(target);
  await button(target, "desktop.ledger.invoices.review").click();
  const missing = label("desktop.ledger.invoices.problem.missing");
  for (const key of [
    "counterparty_name",
    "counterparty_country",
    "currency",
    "invoice_number",
  ])
    await expect(field(target, key)).toHaveAttribute("aria-invalid", "true");
  await expect(editor(target).getByText(missing).first()).toBeVisible();
  await expect(
    editor(target).getByText(
      label("desktop.ledger.invoices.problem.choose_kind"),
    ),
  ).toBeVisible();
  await expect(
    editor(target).getByText(label("desktop.ledger.invoices.problem.no_line")),
  ).toBeVisible();
  await expect(editor(target).locator(".ledger-invoice-confirm")).toHaveCount(
    0,
  );

  await fillIssued(target);
  await field(target, "counterparty_country").fill("ESP");
  await expect(
    editor(target).getByText(
      label("desktop.ledger.invoices.problem.country_letters"),
    ),
  ).toBeVisible();
  await expect(
    editor(target).locator("[data-invariant=country][data-met]"),
  ).toHaveCount(0);
  await field(target, "counterparty_country").fill("ES");

  await field(target, "printed_total").fill("1330.99");
  await expect(
    editor(target).getByText(
      label("desktop.ledger.invoices.problem.printed_differs", {
        total: "1331",
      }),
    ),
  ).toBeVisible();
  await expect(
    editor(target).locator("[data-invariant=totals][data-met]"),
  ).toHaveCount(0);
  await field(target, "printed_total").fill("1331");
  await expect(
    editor(target).locator("[data-invariant=totals][data-met]"),
  ).toHaveCount(1);

  await field(target, "retention_rate").fill("15");
  await field(target, "retention_amount").fill("1200");
  await expect(
    editor(target).getByText(
      label("desktop.ledger.invoices.problem.retention_above_base"),
    ),
  ).toBeVisible();
  await field(target, "retention_amount").fill("0.15");
  await expect(
    editor(target).getByText(
      label("desktop.ledger.invoices.problem.retention_differs", {
        amount: "165",
      }),
    ),
  ).toBeVisible();
  await field(target, "retention_rate").fill("");
  await field(target, "retention_amount").fill("");

  await lineCell(target, 1, 1).fill("1.500");
  await expect(lineCell(target, 1, 1)).toHaveAttribute("aria-invalid", "true");
  await lineCell(target, 1, 1).fill("2");

  await field(target, "invoice_class").selectOption("RECTIFICATIVA");
  await field(target, "series").fill("");
  await expect(
    editor(target).getByText(
      label("desktop.ledger.invoices.problem.series_required"),
    ),
  ).toBeVisible();
  await expect(
    editor(target).getByText(
      label("desktop.ledger.invoices.problem.rectifies_required"),
    ),
  ).toBeVisible();
});

test("an invoice already in the catalogue is refused on its number", async ({
  page: target,
}) => {
  await openInvoices(target);
  await addNew(target);
  await editor(target)
    .getByRole("radio", {
      name: label("desktop.ledger.invoices.kind_choice.issued"),
    })
    .click();
  await field(target, "counterparty_name").fill("Hotel Mirador Azul, S.L.");
  await field(target, "counterparty_tax_id").fill("B00000058");
  await field(target, "counterparty_country").fill("ES");
  await field(target, "series").fill("F");
  await field(target, "invoice_number").fill("F-2026-018");
  await field(target, "issued_at").fill("2026-09-12");
  await field(target, "currency").fill("EUR");
  await lineCell(target, 0, 0).fill("Señalética de recepción");
  await lineCell(target, 0, 1).fill("4");
  await lineCell(target, 0, 2).fill("95.5");
  await lineCell(target, 0, 4).selectOption("RATE_21");
  await button(target, "desktop.ledger.invoices.line.add").click();
  await lineCell(target, 1, 0).fill("Montaje");
  await lineCell(target, 1, 1).fill("3");
  await lineCell(target, 1, 2).fill("40");
  await lineCell(target, 1, 4).selectOption("RATE_21");
  await button(target, "desktop.ledger.invoices.review").click();
  await button(target, "desktop.ledger.invoices.add").click();
  await expect(field(target, "invoice_number")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await expect(
    editor(target).getByText(label("desktop.ledger.invoices.duplicate")),
  ).toBeVisible();
  await button(target, "desktop.ledger.invoices.open_duplicate").click();
  await expect(
    editor(target).getByRole("heading", {
      name: label("desktop.ledger.invoices.title", { number: "F-2026-018" }),
    }),
  ).toBeVisible();
});

test("the next number follows its own series (M7)", async ({
  page: target,
}) => {
  await openInvoices(target);
  await addNew(target);
  await editor(target)
    .getByRole("radio", {
      name: label("desktop.ledger.invoices.kind_choice.issued"),
    })
    .click();
  await field(target, "issued_at").fill("2026-10-23");
  await field(target, "series").fill("F");
  const use = (number: string) =>
    button(target, "desktop.ledger.invoices.use_number", { number });
  await use("F-2026-021").click();
  await expect(field(target, "invoice_number")).toHaveValue("F-2026-021");
  // Another series follows its own numbers, not the highest of all.
  await field(target, "series").fill("T");
  await expect(use("T-2026-0008")).toHaveCount(0);
  await field(target, "invoice_class").selectOption("SIMPLIFICADA");
  await use("T-2026-0008").click();
  await expect(field(target, "invoice_number")).toHaveValue("T-2026-0008");
  // A rectificativa gets none until its series is chosen.
  await field(target, "invoice_class").selectOption("RECTIFICATIVA");
  await field(target, "series").fill("");
  await expect(
    editor(target).getByText(
      label("desktop.ledger.invoices.next_number_series"),
    ),
  ).toBeVisible();
  await field(target, "series").fill("R");
  await expect(use("R-2026-03")).toBeVisible();
  // A received invoice's number is its supplier's: nothing is suggested.
  await editor(target)
    .getByRole("radio", {
      name: label("desktop.ledger.invoices.kind_choice.received"),
    })
    .click();
  await expect(use("R-2026-03")).toHaveCount(0);
});

test("a stored invoice shows its identity and lines as fixed", async ({
  page: target,
}) => {
  await openInvoices(target);
  await allPeriods(target);
  await openStored(target, "F-2026-018");
  await expect(
    editor(target).locator(".ledger-invoice-identity"),
  ).toBeVisible();
  for (const key of [
    "invoice_number",
    "issued_at",
    "currency",
    "counterparty_tax_id",
  ])
    await expect(
      editor(target).getByRole("textbox", {
        name: label(`desktop.ledger.invoices.field.${key}`),
        exact: true,
      }),
    ).toHaveCount(0);
  const fixed = editor(target).locator("[data-fixed]");
  await expect(fixed).toHaveCount(6);
  await expect(fixed.filter({ hasText: "F-2026-018" })).toHaveAttribute(
    "aria-describedby",
    /.+/,
  );
  await expect(
    editor(target).locator(".ledger-invoice-lines input"),
  ).toHaveCount(0);
  await expect(
    editor(target).locator(".ledger-invoice-lines tbody tr"),
  ).toHaveCount(2);
  // Payment status is among what the ledger lets you correct.
  await expect(field(target, "payment_status")).toBeEditable();
});

test("a correction is reviewed and saves only the changed field", async ({
  page: target,
}) => {
  await openInvoices(target);
  await allPeriods(target);
  await openStored(target, "F-2026-018");
  const review = button(target, "desktop.ledger.invoices.review_changes", {
    count: 0,
  });
  await expect(review).toHaveAttribute("aria-disabled", "true");
  await field(target, "payment_status").selectOption("PAID");
  await button(target, "desktop.ledger.invoices.review_changes", {
    count: 1,
  }).click();
  const confirm = editor(target).locator(".ledger-invoice-confirm");
  await expect(confirm.locator("[data-field]")).toHaveCount(1);
  await expect(confirm.locator("[data-field=payment_status]")).toContainText(
    label("desktop.ledger.invoices.payment.paid"),
  );
  await button(target, "desktop.ledger.invoices.save").click();
  await expect(editor(target)).toBeHidden();
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.invoices.saved", { number: "F-2026-018" }),
  );
  await expect(
    dataRows(target).filter({ hasText: "F-2026-018" }),
  ).toContainText(label("desktop.ledger.invoices.payment.paid"));
});

test("an invoice with links cannot be removed; one without can", async ({
  page: target,
}) => {
  await openInvoices(target);
  await allPeriods(target);
  await openStored(target, "CR-2026-0010");
  await button(target, "desktop.ledger.invoices.remove").click();
  await expect(editor(target).locator(".ledger-invoice-remove")).toContainText(
    label("desktop.ledger.invoices.remove_linked"),
  );
  await expect(
    button(target, "desktop.ledger.invoices.remove_confirm"),
  ).toHaveCount(0);
  await button(target, "desktop.ledger.invoices.keep_it").click();
  await button(target, "desktop.ledger.invoices.close").first().click();
  await expect(editor(target)).toBeHidden();

  const before = (await counted(target)).total;
  await openStored(target, "A-1093");
  await button(target, "desktop.ledger.invoices.remove").click();
  await button(target, "desktop.ledger.invoices.remove_confirm").click();
  await expect(editor(target)).toBeHidden();
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.invoices.removed", { number: "A-1093" }),
  );
  await expect.poll(async () => (await counted(target)).total).toBe(before - 1);
  await expect(dataRows(target).filter({ hasText: "A-1093" })).toHaveCount(0);
});

test("leaving an invoice with edits asks before it is discarded", async ({
  page: target,
}) => {
  await openInvoices(target);
  // Untouched, it closes at once.
  await addNew(target);
  await target.keyboard.press("Escape");
  await expect(editor(target)).toBeHidden();

  await addNew(target);
  await field(target, "counterparty_name").fill("Norte Digital S. Coop.");
  await target.keyboard.press("Escape");
  const ask = editor(target).locator(".ledger-invoice-discard");
  await expect(ask).toBeVisible();
  await expect(
    ask.getByRole("button", {
      name: label("desktop.ledger.invoices.keep_editing"),
    }),
  ).toBeFocused();
  await ask
    .getByRole("button", {
      name: label("desktop.ledger.invoices.keep_editing"),
    })
    .click();
  await expect(ask).toBeHidden();
  await expect(field(target, "counterparty_name")).toHaveValue(
    "Norte Digital S. Coop.",
  );
  // The corner close asks the same.
  await editor(target)
    .getByRole("button", {
      name: label("desktop.ledger.invoices.close"),
      exact: true,
    })
    .last()
    .click();
  await expect(ask).toBeVisible();
  await ask
    .getByRole("button", { name: label("desktop.ledger.invoices.discard") })
    .click();
  await expect(editor(target)).toBeHidden();
});

test("a write whose outcome was not seen is shown as unknown and checked, never sent again", async ({
  page: target,
}) => {
  await openInvoices(target, "&ledger=unknown");
  await allPeriods(target);
  await openStored(target, "F-2026-020");
  await field(target, "notes").fill("Reclamada por correo");
  await button(target, "desktop.ledger.invoices.review_changes", {
    count: 1,
  }).click();
  await button(target, "desktop.ledger.invoices.save").click();
  const unknown = editor(target).locator(".ledger-invoice-unknown");
  await expect(unknown).toBeVisible();
  // Nothing more is written until the ledger is read again.
  await expect(button(target, "desktop.ledger.invoices.save")).toHaveCount(0);
  await expect(button(target, "desktop.ledger.invoices.remove")).toHaveCount(0);
  await unknown
    .getByRole("button", { name: label("desktop.ledger.invoices.check") })
    .click();
  await expect(editor(target)).toBeHidden();
  await expect(toast(target)).toHaveText(
    label("desktop.ledger.invoices.saved", { number: "F-2026-020" }),
  );
  // The update went to the ledger once; the check only read it back.
  const calls = await target.evaluate(
    () =>
      (window as unknown as { __scenarioHostCalls?: string[] })
        .__scenarioHostCalls ?? [],
  );
  expect(
    calls.filter((call) => call === "ledger ledger.invoice.update"),
  ).toHaveLength(1);
  expect(calls).toContain("ledger ledger.invoice.view");
});

// ---- Accessibility -------------------------------------------------------------

const engine = readFileSync(
  fileURLToPath(
    new URL("../../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);
async function audit(target: Page, scope: Locator) {
  await target.evaluate(engine);
  const selector = await scope.evaluate((node) => {
    node.setAttribute("data-audit", "");
    return "[data-audit]";
  });
  return target.evaluate(async (context) => {
    const axe = (
      window as unknown as {
        axe: {
          run(
            context: unknown,
            options: unknown,
          ): Promise<{
            violations: { id: string; nodes: { target: string[] }[] }[];
          }>;
        };
      }
    ).axe;
    const result = await axe.run(context, { resultTypes: ["violations"] });
    return result.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.map((node) => node.target.join(" ")),
    }));
  }, selector);
}

for (const scheme of ["light", "dark"] as const)
  test(`the catalogue and both editors have no accessibility violations (${scheme})`, async ({
    page: target,
  }) => {
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
    await openInvoices(target);
    await allPeriods(target);
    await expect(target.locator("html")).toHaveAttribute("data-scheme", scheme);
    expect(await audit(target, section(target))).toEqual([]);
    await addNew(target);
    await fillIssued(target);
    await field(target, "counterparty_country").fill("ESP");
    await button(target, "desktop.ledger.invoices.review").click();
    expect(await audit(target, editor(target))).toEqual([]);
    await field(target, "counterparty_country").fill("ES");
    await button(target, "desktop.ledger.invoices.review").click();
    expect(await audit(target, editor(target))).toEqual([]);
    await target.keyboard.press("Escape");
    await editor(target)
      .locator(".ledger-invoice-discard")
      .getByRole("button", { name: label("desktop.ledger.invoices.discard") })
      .click();
    await openStored(target, "F-2026-018");
    await button(target, "desktop.ledger.invoices.remove").click();
    expect(await audit(target, editor(target))).toEqual([]);
  });
