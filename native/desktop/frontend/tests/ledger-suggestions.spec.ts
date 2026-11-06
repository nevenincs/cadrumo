import "./support/servedLimits";
import { expect, test } from "@playwright/test";
import {
  counterpartyOptions,
  descriptionOptions,
  capitalGoodOptions,
  distinctText,
  emptyFills,
  groupOptions,
  heldThenKnownOptions,
  invoiceNumberOptions,
  lineDescriptionOptions,
  partyNameOptions,
  partyTaxIdOptions,
  referenciaCatastralOptions,
  seriesOptions,
  invoiceCountryOptions,
  usedCodeOptions,
} from "../src/components/ledger/suggestions/ledgerSuggestions";
import {
  factKey,
  statesReference,
} from "../src/components/ledger/assets/assetFields";
import { shownSuggestions } from "../src/components/ui/suggestions";
import type { CatalogueInvoice } from "../src/shell/ledgerInvoiceOperations";
import type {
  KnownCounterparty,
  KnownText,
  LedgerRow,
} from "../src/shell/ledger";
import type { CapitalGood } from "../src/shell/ledgerRegisterOperations";

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

const knownText = (text: string, counterparty: string | null = null) =>
  ({ text, uses: 1, last_used: "2020-01-01", counterparty }) as KnownText;

test("the history follows what is staged and held, and repeats none of it", () => {
  const options = descriptionOptions(
    [row({ description: "Luz", counterparty: "Eléctrica" })],
    ["Alquiler"],
    [
      knownText("ALQUILER"),
      knownText("luz"),
      knownText("Colegio", "Colegio Profesional"),
    ],
  );
  expect(options.map((option) => option.value)).toEqual([
    "Alquiler",
    "Luz",
    "Colegio",
  ]);
  expect(options[2]!.fills).toEqual({ counterparty: "Colegio Profesional" });
});

test("a party of the history fills country and state, and is found by its tax id", () => {
  const known: KnownCounterparty[] = [
    {
      name: "Norte, S.L.",
      tax_id: "B00000001",
      country: "ES",
      identification_state: "ES",
      uses: 3,
      last_used: "2020-01-01",
    },
  ];
  const options = counterpartyOptions([], null, [], known);
  expect(options[0]!.note).toBe("B00000001 · ES");
  expect(options[0]!.fills).toEqual({
    counterparty_country: "ES",
    counterparty_identification_state: "ES",
  });
  expect(shownSuggestions(options, "B000").map((o) => o.value)).toEqual([
    "Norte, S.L.",
  ]);
});

test("a group offers staged, held and known labels once", () => {
  const options = groupOptions(
    [{ ...row({}), group_label: "Oficina" }],
    ["Viajes"],
    [knownText("oficina"), knownText("Antigua")],
  );
  expect(options.map((option) => option.value)).toEqual([
    "Viajes",
    "Oficina",
    "Antigua",
  ]);
});

test("a free text of the history comes after the held rows' own", () => {
  expect(
    heldThenKnownOptions(
      ["P-1", null],
      [knownText("p-1"), knownText("P-2")],
    ).map((option) => option.value),
  ).toEqual(["P-1", "P-2"]);
});

test("an element's stated references offer the history's, and only those", () => {
  for (const reference of [
    factKey(["low_value", "election_reference"]),
    factKey(["used_original_price", "evidence_reference"]),
    factKey(["research_development_evidence_reference"]),
    "vehicle_evidence",
  ])
    expect(statesReference(reference), reference).toBe(true);
  for (const other of [
    "acquisition_reference",
    "name",
    "supplier_name",
    factKey(["authority_class_key"]),
  ])
    expect(statesReference(other), other).toBe(false);
});

test("a capital good is offered by its identifier, this year's first", () => {
  const good = (identifier: string, acquisition_year: number) =>
    ({ identifier, acquisition_year, description: "Nave" }) as CapitalGood;
  const options = capitalGoodOptions([good("A", 2024), good("B", 2026)], 2026);
  expect(options.map((option) => option.value)).toEqual(["B", "A"]);
  expect(options[0]!.note).toBe("Nave");
  expect(options[0]!.fills).toBeUndefined();
});

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

test("an invoice number is noted with its date as the window writes it", () => {
  const offered = invoiceNumberOptions(
    [invoice({ issued_at: "2026-01-05", counterparty_name: "Norte, S.L." })],
    {},
    "en",
  );
  expect(offered.map((one) => one.note)).toEqual(["Jan 5, 2026 · Norte, S.L."]);
});

test("a pick offers no tax decision", () => {
  const offered = [
    ...partyNameOptions([invoice({})]),
    ...invoiceNumberOptions([invoice({})], {}, "en"),
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

test("a served code list follows what the records use, named and in name order", () => {
  const names: Record<string, string> = {
    DE: "Germany",
    ES: "Spain",
    FR: "France",
    AT: "Austria",
  };
  const offered = usedCodeOptions(
    ["FR", "ES", "ES", null],
    (code) => names[code],
    { codes: ["AT", "DE", "ES", "FR"], locale: "en" },
  );
  expect(offered.map(({ value }) => value)).toEqual(["ES", "FR", "AT", "DE"]);
  expect(offered.map(({ note }) => note)).toEqual([
    "Spain",
    "France",
    "Austria",
    "Germany",
  ]);
});

test("with no served list only what the records use is offered", () => {
  expect(usedCodeOptions(["ZZ"]).map(({ value }) => value)).toEqual(["ZZ"]);
  expect(invoiceCountryOptions([], "en", null)).toEqual([]);
  expect(
    invoiceCountryOptions([], "en", ["PT"]).map(({ value }) => value),
  ).toEqual(["PT"]);
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

test("a cadastral reference the leases record is offered once, newest first", () => {
  const options = referenciaCatastralOptions([
    invoice({
      referencia_catastral: "9999999VH9999S0001AB",
      issued_at: "2026-01-05",
    }),
    invoice({ referencia_catastral: null, issued_at: "2026-09-01" }),
    invoice({
      referencia_catastral: "8888888VH8888S0001CD",
      issued_at: "2026-05-01",
    }),
    invoice({
      referencia_catastral: "9999999vh9999s0001ab",
      issued_at: "2026-02-01",
    }),
  ]);
  expect(options.map((option) => option.value)).toEqual([
    "8888888VH8888S0001CD",
    "9999999vh9999s0001ab",
  ]);
  expect(
    referenciaCatastralOptions([invoice({ referencia_catastral: null })]),
  ).toEqual([]);
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
