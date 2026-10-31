import { expect, test } from "@playwright/test";
import {
  counterpartyOptions,
  descriptionOptions,
  distinctText,
  emptyFills,
  invoiceNumberOptions,
  lineDescriptionOptions,
  partyNameOptions,
  partyTaxIdOptions,
  seriesOptions,
  usedCodeOptions,
} from "../src/components/ledger/suggestions/ledgerSuggestions";
import { shownSuggestions } from "../src/components/ui/suggestions";
import type { CatalogueInvoice, LedgerRow } from "../src/shell/ledger";

// What the ledger's own records offer a field. No page is opened.

const invoice = (changes: Partial<CatalogueInvoice>) =>
  ({
    kind: "issued",
    invoice_number: "1",
    invoice_class: "COMPLETA",
    issued_at: "2026-01-01",
    counterparty_name: "Norte, S.L.",
    counterparty_tax_id: "B00000001",
    counterparty_country: "ES",
    series: null,
    lines: [],
    ...changes,
  }) as unknown as CatalogueInvoice;

const row = (changes: Partial<LedgerRow["transaction"]>) =>
  ({
    group_label: null,
    transaction: {
      date: "2026-01-01",
      description: "",
      counterparty: "",
      counterparty_country: null,
      counterparty_identification_state: null,
      ...changes,
    },
  }) as unknown as LedgerRow;

test("a name under two tax ids stays two parties, told apart by the note", () => {
  const options = partyNameOptions([
    invoice({ counterparty_tax_id: "B00000001", issued_at: "2026-02-01" }),
    invoice({ counterparty_tax_id: "B00000002", issued_at: "2026-03-01" }),
  ]);
  expect(options.map((option) => option.value)).toEqual([
    "Norte, S.L.",
    "Norte, S.L.",
  ]);
  expect(options[0]!.note).toBe("B00000002 · ES");
  expect(options[0]!.fills).toEqual({
    name: "Norte, S.L.",
    tax_id: "B00000002",
    country: "ES",
  });
});

test("a tax id finds a party in the name field, and a name in the tax id field", () => {
  const invoices = [invoice({})];
  expect(
    shownSuggestions(partyNameOptions(invoices), "B000").map(
      (option) => option.label,
    ),
  ).toEqual(["Norte, S.L."]);
  expect(
    shownSuggestions(partyTaxIdOptions(invoices), "norte").map(
      (option) => option.label,
    ),
  ).toEqual(["B00000001"]);
});

test("the same kind ranks first, then the newest", () => {
  const options = partyNameOptions(
    [
      invoice({
        kind: "issued",
        counterparty_name: "Issued",
        counterparty_tax_id: "A",
        issued_at: "2026-09-01",
      }),
      invoice({
        kind: "received",
        counterparty_name: "Old received",
        counterparty_tax_id: "B",
        issued_at: "2026-01-01",
      }),
      invoice({
        kind: "received",
        counterparty_name: "New received",
        counterparty_tax_id: "C",
        issued_at: "2026-02-01",
      }),
    ],
    { kind: "received" },
  );
  expect(options.map((option) => option.value)).toEqual([
    "New received",
    "Old received",
    "Issued",
  ]);
});

test("a fill reaches only what is still empty", () => {
  expect(
    emptyFills(
      { name: "Norte", tax_id: "B1", country: "ES" },
      { name: "typed", taxId: " ", country: "FR" },
      { name: "name", tax_id: "taxId", country: "country" },
    ),
  ).toEqual([["taxId", "B1"]]);
  expect(emptyFills(undefined, {}, { name: "name" })).toEqual([]);
});

test("a pick offers no tax decision", () => {
  const offered = [
    ...partyNameOptions([invoice({})]),
    ...invoiceNumberOptions([invoice({})]),
    ...descriptionOptions([row({ description: "Rent", counterparty: "Lar" })]),
    ...counterpartyOptions(
      [row({ counterparty: "Lar", counterparty_country: "ES" })],
      null,
    ),
  ];
  const keys = new Set(offered.flatMap((one) => Object.keys(one.fills ?? {})));
  for (const key of keys)
    expect([
      "name",
      "tax_id",
      "country",
      "counterparty",
      "counterparty_country",
      "counterparty_identification_state",
    ]).toContain(key);
});

test("text is offered once by its folded spelling, the newest spelling kept", () => {
  expect(distinctText(["Café", "CAFE ", null, "", "te"])).toEqual([
    "Café",
    "te",
  ]);
});

test("a line description of this party comes first", () => {
  const options = lineDescriptionOptions(
    [
      invoice({
        counterparty_name: "Other",
        issued_at: "2026-09-01",
        lines: [{ description: "Theirs" }] as CatalogueInvoice["lines"],
      }),
      invoice({
        counterparty_name: "Norte, S.L.",
        lines: [{ description: "Ours" }] as CatalogueInvoice["lines"],
      }),
    ],
    "norte, s.l.",
  );
  expect(options.map((option) => option.value)).toEqual(["Ours", "Theirs"]);
});

test("a series of the same kind and class comes first", () => {
  const options = seriesOptions(
    [
      invoice({ series: "R", invoice_class: "RECTIFICATIVA" }),
      invoice({ series: "F" }),
    ],
    { kind: "issued", invoiceClass: "COMPLETA" },
  );
  expect(options.map((option) => option.value)).toEqual(["F", "R"]);
});

test("codes in use are offered most used first, in capitals", () => {
  expect(
    usedCodeOptions(["es", "FR", "ES", null]).map((option) => option.value),
  ).toEqual(["ES", "FR"]);
});

test("a list hides when its one answer is what the field holds", () => {
  const options = [{ value: "F", label: "F" }];
  expect(shownSuggestions(options, "F")).toEqual([]);
  expect(shownSuggestions(options, "")).toEqual(options);
});

test("a list shows at most eight", () => {
  const options = Array.from({ length: 12 }, (_, at) => ({
    value: `v${at}`,
    label: `v${at}`,
  }));
  expect(shownSuggestions(options, "v")).toHaveLength(8);
});
