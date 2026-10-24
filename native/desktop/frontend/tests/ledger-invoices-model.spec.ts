import { expect, test } from "@playwright/test";
import type { CatalogueInvoice } from "../src/shell/ledger";
import {
  NO_FILTER,
  checkCorrection,
  checkDraft,
  correctionOf,
  emptyDraft,
  filterCatalogue,
  holdsCorrection,
  isAddedInvoice,
  lineFigures,
  retentionFigures,
  sortCatalogue,
  suggestNumber,
  sumDecimals,
  timesToCent,
  type InvoiceDraft,
  type LineDraft,
} from "../src/components/ledger/invoices/invoiceModel";

// The invoice editor's arithmetic and checks, against figures worked out by
// hand, and the catalogue's own filter, sort and next-number rules over
// synthetic invoices.

function invoice(facts: Partial<CatalogueInvoice> = {}): CatalogueInvoice {
  return {
    invoice_id: "a".repeat(64),
    bucket_id: null,
    kind: "issued",
    invoice_number: "F-2026-001",
    issued_at: "2026-03-02",
    counterparty_name: "Talleres Ondara, S.L.",
    counterparty_tax_id: "B00000017",
    counterparty_country: "ES",
    base_total: { decimal: "1000.00" },
    iva_total: { decimal: "210.00" },
    grand_total: { decimal: "1210.00" },
    currency: "EUR",
    payment_status: "PENDING",
    linked_transaction_ids: [],
    source_filename: null,
    source_sha256: null,
    source_row_index: null,
    notes: "",
    retention_rate: null,
    retention_amount: null,
    recargo_amount: null,
    operation_type: null,
    lines: [],
    invoice_class: "ORDINARIA",
    series: "F",
    operation_date: null,
    operation_date_role: null,
    iva_category: null,
    rectifies_invoice_number: null,
    fx_rate: null,
    fx_rate_date: null,
    fx_rate_source: null,
    base_total_eur: null,
    iva_total_eur: null,
    grand_total_eur: null,
    ...facts,
  };
}

const line = (facts: Partial<LineDraft>): LineDraft => ({
  key: "l1",
  description: "Diseño",
  quantity: "1",
  unitPrice: "",
  rate: "",
  category: "",
  ...facts,
});

function filled(facts: Partial<InvoiceDraft> = {}): InvoiceDraft {
  return {
    ...emptyDraft("l1"),
    kind: "issued",
    number: "F-2026-021",
    issuedAt: "2026-10-23",
    counterpartyName: "Norte Digital S. Coop.",
    taxId: "F00000022",
    country: "es",
    currency: "eur",
    lines: [
      line({ key: "l1", unitPrice: "550", rate: "RATE_21" }),
      line({ key: "l2", quantity: "2", unitPrice: "275", rate: "RATE_21" }),
    ],
    ...facts,
  };
}

test("exact decimal sums and products round to the cent", () => {
  expect(sumDecimals(["0.1", "0.2"])).toBe("0.3");
  expect(timesToCent("3", "33.333333")).toBe("100");
  expect(timesToCent("2.5", "0.21")).toBe("0.53");
  expect(timesToCent("19.99", "0.21")).toBe("4.2");
});

test("a line's subtotal and IVA come from its quantity, price and slot", () => {
  const priced = lineFigures(
    line({ quantity: "3", unitPrice: "12.5", rate: "RATE_21" }),
  );
  expect(priced).toMatchObject({
    complete: true,
    subtotal: "37.5",
    iva: "7.88",
  });
  expect(lineFigures(line({ unitPrice: "100", rate: "RATE_7.5" })).iva).toBe(
    "7.5",
  );
  expect(lineFigures(line({ unitPrice: "80", rate: "EXEMPT" })).iva).toBe("0");
  // No rate is chosen for the person.
  const unrated = lineFigures(line({ unitPrice: "80" }));
  expect(unrated.complete).toBe(false);
  expect(unrated.problems.rate).toEqual({ kind: "rule", rule: "choose_rate" });
  // Quantities go through the one number grammar.
  const grouped = lineFigures(
    line({ quantity: "1.500", unitPrice: "2", rate: "RATE_21" }),
  );
  expect(grouped.problems.quantity).toMatchObject({
    kind: "grammar",
    refusal: { key: "ambiguous_grouping" },
  });
  expect(
    lineFigures(line({ quantity: "0", unitPrice: "2", rate: "RATE_21" }))
      .problems.quantity,
  ).toMatchObject({ refusal: { key: "zero" } });
  // An untouched line, with only its opening quantity, is not entered.
  expect(lineFigures(line({ description: "" })).entered).toBe(false);
});

test("two lines at 21% with a 15% retención add up as the invoice prints", () => {
  const check = checkDraft(filled({ retentionRate: "15" }));
  expect(check.totals).toEqual({
    base: "1100",
    iva: "231",
    recargo: null,
    total: "1331",
  });
  expect(check.retention).toMatchObject({
    rate: "0.15",
    amount: "165",
    implied: "165",
  });
  expect(check.invariants).toEqual({
    counterparty: true,
    country: true,
    line: true,
    totals: true,
  });
  expect(check.problems).toEqual({});
  expect(check.request).toEqual({
    kind: "issued",
    counterparty_name: "Norte Digital S. Coop.",
    counterparty_tax_id: "F00000022",
    counterparty_country: "ES",
    invoice_number: "F-2026-021",
    issued_at: "2026-10-23",
    currency: "EUR",
    notes: "",
    invoice_class: "ORDINARIA",
    lines: [
      {
        description: "Diseño",
        quantity: { decimal: "1" },
        unit_price: { decimal: "550" },
        subtotal: { decimal: "550" },
        iva_rate: "RATE_21",
        iva_amount: { decimal: "115.5" },
      },
      {
        description: "Diseño",
        quantity: { decimal: "2" },
        unit_price: { decimal: "275" },
        subtotal: { decimal: "550" },
        iva_rate: "RATE_21",
        iva_amount: { decimal: "115.5" },
      },
    ],
    retention_rate: { decimal: "0.15" },
    retention_amount: { decimal: "165" },
  });
});

test("nothing is assumed: no kind, country, currency or line until given", () => {
  const check = checkDraft(emptyDraft("l1"));
  expect(check.request).toBeNull();
  expect(check.problems.kind).toEqual({ kind: "rule", rule: "choose_kind" });
  expect(check.problems.counterparty_country).toEqual({ kind: "missing" });
  expect(check.problems.currency).toEqual({ kind: "missing" });
  expect(check.problems.lines).toEqual({ kind: "rule", rule: "no_line" });
  expect(check.invariants).toEqual({
    counterparty: false,
    country: false,
    line: false,
    totals: false,
  });
});

test("each creation invariant and rule refuses on its own field", () => {
  expect(
    checkDraft(filled({ counterpartyName: " " })).problems.counterparty_name,
  ).toEqual({
    kind: "missing",
  });
  expect(
    checkDraft(filled({ country: "ESP" })).problems.counterparty_country,
  ).toEqual({
    kind: "rule",
    rule: "country_letters",
  });
  const unfinished = checkDraft(
    filled({
      lines: [line({ key: "l9", description: "Montaje", unitPrice: "40" })],
    }),
  );
  expect(unfinished.invariants.line).toBe(false);
  expect(unfinished.problems["line:l9:rate"]).toEqual({
    kind: "rule",
    rule: "choose_rate",
  });
  const printed = checkDraft(filled({ printedTotal: "1330.99" }));
  expect(printed.invariants.totals).toBe(false);
  expect(printed.problems.printed).toEqual({
    kind: "rule",
    rule: "printed_differs",
    values: { total: "1331" },
  });
  expect(checkDraft(filled({ recargo: "231.01" })).problems.recargo).toEqual({
    kind: "rule",
    rule: "recargo_above_iva",
  });
  expect(
    checkDraft(
      filled({
        retentionRate: "15",
        retentionAmount: "1101",
        retentionTouched: true,
      }),
    ).problems.retention_amount,
  ).toEqual({ kind: "rule", rule: "retention_above_base" });
  expect(
    checkDraft(
      filled({
        retentionRate: "15",
        retentionAmount: "160",
        retentionTouched: true,
      }),
    ).problems.retention_amount,
  ).toMatchObject({ rule: "retention_differs" });
  expect(
    checkDraft(filled({ retentionRate: "0.15" })).problems.retention_rate,
  ).toMatchObject({
    refusal: { key: "percent_as_fraction", suggestion: "15" },
  });
  const rectificativa = checkDraft(
    filled({ invoiceClass: "RECTIFICATIVA", series: "" }),
  );
  expect(rectificativa.problems.series).toEqual({
    kind: "rule",
    rule: "series_required",
  });
  expect(rectificativa.problems.rectifies_invoice_number).toEqual({
    kind: "rule",
    rule: "rectifies_required",
  });
  expect(
    checkDraft(filled({ taxId: "" })).problems.counterparty_tax_id,
  ).toEqual({
    kind: "rule",
    rule: "tax_id_required",
  });
  // An issued simplificada may leave the tax id out.
  expect(
    checkDraft(filled({ taxId: "", invoiceClass: "SIMPLIFICADA" })).problems,
  ).toEqual({});
});

test("a retención amount can stand alone; a rate cannot", () => {
  expect(retentionFigures("1000", "", "150").problems).toEqual({});
  expect(retentionFigures("1000", "15", "").problems.amount).toEqual({
    kind: "rule",
    rule: "retention_needs_amount",
  });
  expect(retentionFigures("1000", "15", "150.01").problems).toEqual({});
});

test("the next number follows the highest in its series, class and year", () => {
  const catalogue = [
    invoice({
      invoice_id: "1".repeat(64),
      invoice_number: "F-2026-018",
      issued_at: "2026-09-12",
    }),
    invoice({
      invoice_id: "2".repeat(64),
      invoice_number: "F-2026-020",
      issued_at: "2026-10-10",
    }),
    invoice({
      invoice_id: "3".repeat(64),
      invoice_number: "F-2025-099",
      issued_at: "2025-12-18",
    }),
    ...["2026-007", "2026-031", "2026-009"].map((number, at) =>
      invoice({
        invoice_id: String(4 + at).repeat(64),
        invoice_number: number,
        series: "2026",
        issued_at: "2026-05-01",
      }),
    ),
    invoice({
      invoice_id: "8".repeat(64),
      invoice_number: "T-2026-0007",
      series: "T",
      invoice_class: "SIMPLIFICADA",
    }),
    invoice({
      invoice_id: "9".repeat(64),
      invoice_number: "R-2026-02",
      series: "R",
      invoice_class: "RECTIFICATIVA",
    }),
    invoice({
      invoice_id: "c".repeat(64),
      kind: "received",
      invoice_number: "F-2026-500",
    }),
  ];
  const ask = (
    series: string,
    invoiceClass: "ORDINARIA" | "SIMPLIFICADA" | "RECTIFICATIVA" = "ORDINARIA",
    year = 2026,
  ) => suggestNumber(catalogue, { kind: "issued", invoiceClass, series, year });
  expect(ask("F")).toEqual({ series: "F", number: "F-2026-021" });
  // With no series typed, the class's most used series that year.
  expect(ask("")).toEqual({ series: "2026", number: "2026-032" });
  expect(ask("", "SIMPLIFICADA")).toEqual({
    series: "T",
    number: "T-2026-0008",
  });
  expect(ask("", "RECTIFICATIVA")).toBeNull();
  expect(ask("R", "RECTIFICATIVA")).toEqual({
    series: "R",
    number: "R-2026-03",
  });
  expect(ask("F", "ORDINARIA", 2025)).toEqual({
    series: "F",
    number: "F-2025-100",
  });
  // Nothing to follow: no suggestion is made up.
  expect(ask("Z")).toBeNull();
  expect(
    suggestNumber(catalogue, {
      kind: "received",
      invoiceClass: "ORDINARIA",
      series: "F",
      year: 2026,
    }),
  ).toBeNull();
});

test("a correction sends only the changed fields the update accepts", () => {
  const stored = invoice({
    retention_rate: { decimal: "0.15" },
    retention_amount: { decimal: "150.00" },
    operation_date: "2026-03-01",
    operation_date_role: "OPERATION_PERFORMED",
  });
  const draft = correctionOf(stored);
  expect(draft.retentionRate).toBe("15");
  expect(checkCorrection(stored, draft)).toMatchObject({
    changed: [],
    request: null,
  });
  const paid = checkCorrection(stored, {
    ...draft,
    paymentStatus: "PAID",
    notes: "Cobrada",
  });
  expect(paid.request).toEqual({
    invoice_id: stored.invoice_id,
    patch: {
      values: { notes: "Cobrada", payment_status: "PAID" },
      fields: ["notes", "payment_status"],
    },
  });
  expect(
    holdsCorrection(
      { ...stored, notes: "Cobrada", payment_status: "PAID" },
      paid.request!,
    ),
  ).toBe(true);
  expect(holdsCorrection(stored, paid.request!)).toBe(false);
  // A new rate works the amount out again.
  const seven = checkCorrection(stored, {
    ...draft,
    retentionRate: "7",
    retentionTouched: false,
  });
  expect(seven.request?.patch.values).toEqual({
    retention_rate: { decimal: "0.07" },
    retention_amount: { decimal: "70" },
  });
  // An operation date with its role can move but not go.
  expect(
    checkCorrection(stored, { ...draft, operationDate: "" }).problems
      .operation_date,
  ).toEqual({
    kind: "rule",
    rule: "operation_date_fixed",
  });
  expect(
    checkCorrection(invoice(), {
      ...correctionOf(invoice()),
      operationDate: "2026-03-01",
    }).problems.operation_date,
  ).toEqual({ kind: "rule", rule: "operation_date_fixed" });
  // Leaving the rectificativa class takes its number away.
  const rectified = invoice({
    invoice_class: "RECTIFICATIVA",
    rectifies_invoice_number: "F-2026-001",
  });
  expect(
    checkCorrection(rectified, {
      ...correctionOf(rectified),
      invoiceClass: "ORDINARIA",
    }).request?.patch,
  ).toEqual({
    values: { invoice_class: "ORDINARIA", rectifies_invoice_number: null },
    fields: ["invoice_class", "rectifies_invoice_number"],
  });
  expect(
    checkCorrection(stored, { ...draft, paymentId: "abc" }).problems.payment_id,
  ).toEqual({
    kind: "rule",
    rule: "payment_id_shape",
  });
});

test("an add read back is recognised by its identity", () => {
  const request = checkDraft(filled()).request!;
  const stored = invoice({
    invoice_number: "F-2026-021",
    issued_at: "2026-10-23",
    counterparty_tax_id: "F00000022",
    grand_total: { decimal: "1331.00" },
  });
  expect(isAddedInvoice(stored, request)).toBe(true);
  expect(
    isAddedInvoice({ ...stored, grand_total: { decimal: "1331.01" } }, request),
  ).toBe(false);
});

test("the catalogue filters by kind, class, payment, links, period and words", () => {
  const catalogue = [
    invoice({
      invoice_id: "1".repeat(64),
      invoice_number: "F-2026-001",
      issued_at: "2026-02-01",
    }),
    invoice({
      invoice_id: "2".repeat(64),
      kind: "received",
      invoice_number: "A-1093",
      counterparty_name: "Papelería Trazo",
      issued_at: "2026-10-14",
      payment_status: "CANCELLED",
      grand_total: { decimal: "93.17" },
    }),
    invoice({
      invoice_id: "3".repeat(64),
      invoice_number: "F-2026-002",
      issued_at: "2026-08-01",
      linked_transaction_ids: ["f".repeat(64)],
    }),
  ];
  const ids = (found: CatalogueInvoice[]) =>
    found.map((item) => item.invoice_number);
  expect(
    ids(filterCatalogue(catalogue, { ...NO_FILTER, kind: "received" })),
  ).toEqual(["A-1093"]);
  expect(
    ids(filterCatalogue(catalogue, { ...NO_FILTER, unmatched: true })),
  ).toEqual(["F-2026-001", "A-1093"]);
  expect(
    ids(filterCatalogue(catalogue, { ...NO_FILTER, payment: "CANCELLED" })),
  ).toEqual(["A-1093"]);
  expect(
    ids(
      filterCatalogue(catalogue, {
        ...NO_FILTER,
        period: { year: 2026, code: "3T" },
      }),
    ),
  ).toEqual(["F-2026-002"]);
  expect(
    ids(
      filterCatalogue(catalogue, { ...NO_FILTER, search: "papeleria 93,17" }),
    ),
  ).toEqual(["A-1093"]);
  expect(
    ids(sortCatalogue(catalogue, { key: "total", direction: "asc" })),
  ).toEqual(["A-1093", "F-2026-002", "F-2026-001"]);
  expect(
    ids(sortCatalogue(catalogue, { key: "date", direction: "desc" })),
  ).toEqual(["A-1093", "F-2026-002", "F-2026-001"]);
});
