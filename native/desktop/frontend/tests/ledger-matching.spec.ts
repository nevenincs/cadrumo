import { expect, test } from "@playwright/test";
import type { CatalogueInvoice } from "../src/shell/ledger";
import {
  inconsistencies,
  linkPicker,
  linkAction,
  reconcile,
  settlement,
  tiedInvoices,
  tiedMovements,
} from "../src/components/ledger/matching/matchingModel";
import { hexId, movement } from "./support/ledger";

// Matching suggests at most one invoice per movement and one movement per
// invoice, by the product's settlement rule, ranked by the invoice number
// in the description, the issue-to-payment gap, the counterparty and the
// amount. Equal candidates are ambiguous, and a staged link withdraws every
// suggestion that competes with it. Every value is invented.

function invoice(
  number: string,
  facts: Partial<CatalogueInvoice> & { total?: string } = {},
): CatalogueInvoice {
  const { total = "36.30", ...rest } = facts;
  return {
    invoice_id: hexId(`inv-${number}`),
    bucket_id: null,
    kind: "received",
    invoice_number: number,
    issued_at: "2026-10-01",
    counterparty_name: "Papelería Trazo SL",
    counterparty_tax_id: "B12000045",
    counterparty_country: "ES",
    base_total: { decimal: "30.00" },
    iva_total: { decimal: "6.30" },
    grand_total: { decimal: total },
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
    series: null,
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
    ...rest,
  };
}

test("a candidate settles the total less its retención, on the invoice's flow and currency, to the cent", () => {
  const withheld = invoice("F-1", {
    kind: "issued",
    total: "1210.00",
    retention_amount: { decimal: "150.00" },
  });
  expect(settlement(withheld)).toBe("1060.00");
  const paid = movement("a", { amount: "1060", direction: "INCOMING" });
  const off = movement("b", { amount: "1060.02", direction: "INCOMING" });
  const cent = movement("c", { amount: "1060.01", direction: "INCOMING" });
  const wrongWay = movement("d", { amount: "1060", direction: "OUTGOING" });
  const foreign = movement("e", {
    amount: "1060",
    direction: "INCOMING",
    currency: "USD",
  });
  const transfer = movement("f", {
    amount: "1060",
    direction: "INTERNAL_TRANSFER",
  });
  const found = reconcile(
    [paid, off, cent, wrongWay, foreign, transfer],
    [withheld],
  );
  expect(
    found.pairs.map((pair) => pair.row.transaction.transaction_id).sort(),
  ).toEqual(["a", "c"]);
});

test("already linked invoices and movements are never suggested", () => {
  const linked = invoice("L-1", { linked_transaction_ids: ["x"] });
  const open = invoice("L-2");
  const cites = movement("cites", { invoice_id: "other" });
  const free = movement("free");
  const archived = movement("gone", { lifecycle_state: "ARCHIVED" });
  const found = reconcile([cites, free, archived], [linked, open]);
  expect(found.pairs).toHaveLength(1);
  expect(found.best.get("free")?.invoice.invoice_number).toBe("L-2");
});

test("the invoice number in the description outranks the gap, the gap the counterparty, the counterparty the amount", () => {
  const row = movement("m", {
    date: "2026-10-10",
    amount: "36.30",
    description: "PAGO FRA PT-0412 TRAZO",
    counterparty: "Otra Empresa",
  });
  const numbered = invoice("PT-0412", { issued_at: "2026-08-01" });
  const close = invoice("PT-0999", {
    issued_at: "2026-10-09",
    counterparty_name: "Otra Empresa SL",
  });
  const found = reconcile([row], [close, numbered]);
  const best = found.best.get("m")!;
  expect(best.invoice.invoice_number).toBe("PT-0412");
  expect(best.ambiguous).toBe(false);
  expect(best.chips.map((chip) => chip.kind)).toEqual([
    "number",
    "gap",
    "amount",
  ]);
  expect(best.others.map((other) => other.invoice.invoice_number)).toEqual([
    "PT-0999",
  ]);

  // Without a number, the shorter gap wins over the counterparty.
  const plain = movement("p", {
    date: "2026-10-10",
    description: "TRANSFERENCIA",
    counterparty: "Papelería Trazo",
  });
  const sameParty = invoice("A-1", { issued_at: "2026-09-01" });
  const nearer = invoice("B-1", {
    issued_at: "2026-10-08",
    counterparty_name: "Nadie SA",
  });
  expect(
    reconcile([plain], [sameParty, nearer]).best.get("p")?.invoice
      .invoice_number,
  ).toBe("B-1");
  // A payment long before the invoice ranks after every one made after it.
  const early = invoice("C-1", { issued_at: "2026-11-30" });
  const late = invoice("D-1", { issued_at: "2026-07-01" });
  expect(
    reconcile([plain], [early, late]).best.get("p")?.invoice.invoice_number,
  ).toBe("D-1");
});

test("each invoice is offered to one movement and each movement gets one invoice", () => {
  const first = movement("first", {
    date: "2026-10-03",
    counterparty: "Papelería Trazo",
  });
  const second = movement("second", {
    date: "2026-10-20",
    counterparty: "Papelería Trazo",
  });
  const only = invoice("ONE-1", { issued_at: "2026-10-02" });
  const found = reconcile([first, second], [only]);
  expect([...found.best.keys()]).toEqual(["first"]);
  expect(found.pairs).toHaveLength(2);
});

test("equal candidates are ambiguous: tied invoices open a chooser and tied movements point at each other", () => {
  const row = movement("row", { date: "2026-10-06", counterparty: "Arroyo" });
  const left = invoice("AA-118", { counterparty_name: "Arroyo Asesores" });
  const right = invoice("AA-119", { counterparty_name: "Arroyo Asesores" });
  const tied = reconcile([row], [left, right]).best.get("row")!;
  expect(tied.ambiguous).toBe(true);
  expect(
    tiedInvoices(tied)
      .map((pair) => pair.invoice.invoice_number)
      .sort(),
  ).toEqual(["AA-118", "AA-119"]);

  const a = movement("a", { date: "2026-10-12", direction: "INCOMING" });
  const b = movement("b", { date: "2026-10-12", direction: "INCOMING" });
  const issued = invoice("N-5", { kind: "issued", issued_at: "2026-10-09" });
  const both = reconcile([a, b], [issued]);
  expect([...both.best.keys()].sort()).toEqual(["a", "b"]);
  for (const id of ["a", "b"]) {
    const suggestion = both.best.get(id)!;
    expect(suggestion.ambiguous).toBe(true);
    expect(tiedInvoices(suggestion)).toEqual([]);
    expect(
      tiedMovements(suggestion).map(
        (pair) => pair.row.transaction.transaction_id,
      ),
    ).toEqual([id === "a" ? "b" : "a"]);
  }
});

test("staging a link withdraws every suggestion that uses the same invoice or movement", () => {
  const a = movement("a", { date: "2026-10-12", direction: "INCOMING" });
  const b = movement("b", { date: "2026-10-12", direction: "INCOMING" });
  const issued = invoice("N-5", { kind: "issued", issued_at: "2026-10-09" });
  const other = invoice("N-6", { kind: "issued", issued_at: "2026-09-01" });
  const staged = [linkAction("a", issued.invoice_id)];
  const found = reconcile([a, b], [issued, other], staged);
  expect(found.best.has("a")).toBe(false);
  // The rival takes the other invoice; the staged one is offered to no one.
  expect(found.best.get("b")?.invoice.invoice_number).toBe("N-6");
  expect(
    found.pairs.some((pair) => pair.invoice.invoice_id === issued.invoice_id),
  ).toBe(false);
});

test("the picker sorts by whether an invoice settles and shows what is staged or linked", () => {
  const row = movement("row");
  const settlesIt = invoice("S-1");
  const elsewhere = invoice("S-2", { linked_transaction_ids: ["zzz"] });
  const takenBy = invoice("S-3");
  const different = invoice("O-1", { total: "99.00" });
  const issued = invoice("I-1", { kind: "issued" });
  const picker = linkPicker(
    row,
    [settlesIt, elsewhere, takenBy, different, issued],
    [linkAction("rival", takenBy.invoice_id)],
  );
  expect(
    picker.settles.map((option) => option.invoice.invoice_number).sort(),
  ).toEqual(["S-1", "S-2", "S-3"]);
  expect(picker.other.map((option) => option.invoice.invoice_number)).toEqual([
    "O-1",
  ]);
  const by = new Map(
    [...picker.settles, ...picker.other].map((option) => [
      option.invoice.invoice_number,
      option,
    ]),
  );
  expect(by.get("S-2")?.linked).toBe(1);
  expect(by.get("S-3")?.stagedFor).toBe("rival");
  expect(by.get("S-1")?.stagedFor).toBeNull();
});

test("a one-sided link is repaired by a link only where both sides end up citing each other", () => {
  const lists = invoice("LISTS", { linked_transaction_ids: ["free"] });
  const cited = invoice("CITED");
  const free = movement("free");
  const citesOther = movement("cites", { invoice_id: hexId("inv-ELSEWHERE") });
  const listsCiting = invoice("LISTS-2", { linked_transaction_ids: ["cites"] });
  const citing = movement("citing", { invoice_id: cited.invoice_id });
  const found = inconsistencies(
    [
      {
        invoice_id: lists.invoice_id,
        transaction_id: "free",
        direction: "invoice-only",
      },
      {
        invoice_id: listsCiting.invoice_id,
        transaction_id: "cites",
        direction: "invoice-only",
      },
      {
        invoice_id: cited.invoice_id,
        transaction_id: "citing",
        direction: "transaction-only",
      },
      {
        invoice_id: hexId("inv-GONE"),
        transaction_id: "citing",
        direction: "transaction-only",
      },
      {
        invoice_id: lists.invoice_id,
        transaction_id: "unread",
        direction: "invoice-only",
      },
    ],
    [free, citesOther, citing],
    [lists, cited, listsCiting],
  );
  expect(found.map((item) => item.repair)).toEqual([
    { kind: "link" },
    { kind: "none", why: "cites_another" },
    { kind: "link" },
    { kind: "none", why: "invoice_missing" },
    { kind: "none", why: "not_loaded" },
  ]);
});
