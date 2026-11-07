import { servedLimits } from "./support/servedLimits";
import { windowFixture } from "./support/windowFixtures";
import { holdRecordedPeriods } from "../src/dev/periodRecording";
import { holdLedgerLimits } from "../src/shell/ledgerLimits";
import { holdLedgerPeriods } from "../src/shell/ledgerPeriods";
import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { readLocaleDecimal } from "../src/shared/numbers";
import type {
  CatalogueInvoice,
  InvoicePreviewRequest,
  InvoicePreviewResult,
} from "../src/shell/ledgerInvoiceOperations";
import {
  InvoicePreviewSession,
  type PreviewReply,
} from "../src/components/ledger/invoices/invoicePreview";
import {
  NO_FILTER,
  checkCorrection,
  isPaymentId,
  checkDraft,
  correctionOf,
  correctionPreview,
  emptyDraft,
  filterCatalogue,
  holdsCorrection,
  readDraft,
  sortCatalogue,
  suggestNumber,
  type InvoiceDraft,
  type LineDraft,
} from "../src/components/ledger/invoices/invoiceModel";
import { findingText } from "../src/components/ledger/invoices/invoiceWords";
import { SERVED } from "./support/servedVocabulary";
import { fixtureDay, fixtureYear } from "../src/dev/fixtureDates";
import { servedSupport } from "../src/dev/servedYearAuthority";

const CORRECTIVE = SERVED.correctiveClass;

// How the invoice editor holds the ledger's answer to the draft on the page,
// what it lets through on each answer, and the catalogue's own filter, sort
// and next-number rules. Answers are outputs recorded from the real backend,
// and every figure asserted is one that backend served.

type Recording = {
  request: InvoicePreviewRequest;
  result: InvoicePreviewResult;
};
const recorded = (
  JSON.parse(
    readFileSync(
      windowFixture("ledger-recordings", "ledgerInvoicePreview"),
      "utf8",
    ),
  ) as { recordings: Record<string, Recording> }
).recordings;
const answer = (name: string) => recorded[name]!.result;
/** The counterparty's tax id the recorded drafts were asked with. */
const RECORDED_TAX_ID = recorded.two_lines!.request.counterparty_tax_id!;

function invoice(facts: Partial<CatalogueInvoice> = {}): CatalogueInvoice {
  return {
    invoice_id: "a".repeat(64),
    bucket_id: null,
    kind: "issued",
    invoice_number: `F-${fixtureYear}-001`,
    issued_at: fixtureDay(3, 2),
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
    referencia_catastral: null,
    settlement_amount: { decimal: "1210.00" },
    ...facts,
  };
}

const line = (facts: Partial<LineDraft>): LineDraft => ({
  key: "line-1",
  description: "Diseño de marca",
  quantity: "1",
  unitPrice: "550",
  rate: "RATE_21",
  category: "",
  statedSubtotal: "",
  statedIva: "",
  ...facts,
});

/** The draft of the `two_lines` recording, with what a case states over it. */
function filled(
  facts: Partial<InvoiceDraft> = {},
  first: Partial<LineDraft> = {},
): InvoiceDraft {
  return {
    ...emptyDraft("line-1", SERVED.defaultClass),
    kind: "issued",
    series: "F",
    number: `F-${fixtureYear}-021`,
    issuedAt: fixtureDay(10, 23),
    counterpartyName: "Norte Digital S. Coop.",
    taxId: RECORDED_TAX_ID,
    country: "es",
    currency: "eur",
    lines: [
      line(first),
      line({
        key: "line-2",
        description: "Piezas gráficas",
        quantity: "2",
        unitPrice: "275",
      }),
    ],
    ...facts,
  };
}

/** What the editor knows of a draft once `name` answered it. */
const checked = (draft: InvoiceDraft, name: string | null) =>
  checkDraft(
    draft,
    readDraft(draft, CORRECTIVE),
    name === null ? null : answer(name),
  );

// ---- The session ---------------------------------------------------------------

/** A ledger whose answers the test gives one at a time. */
function ledger() {
  const asked: {
    request: InvoicePreviewRequest;
    reply(reply: PreviewReply): Promise<void>;
  }[] = [];
  const session = new InvoicePreviewSession(
    (request) =>
      new Promise<PreviewReply>((resolve) => {
        asked.push({
          request,
          reply: async (reply) => {
            resolve(reply);
            // Past the session's own continuation.
            await new Promise((settled) => setTimeout(settled));
          },
        });
      }),
    // Long enough that only `commit` sends anything here.
    60_000,
  );
  return { asked, session };
}
const draftA: InvoicePreviewRequest = { issued_at: fixtureDay(10, 23) };
const draftB: InvoicePreviewRequest = { issued_at: fixtureDay(3, 1, -3) };
const said = (name: string): PreviewReply => ({
  kind: "answer",
  result: answer(name),
});

test("an answer counts only for the draft it was asked about, by its digest", async () => {
  const { asked, session } = ledger();
  session.want(draftA);
  expect(session.snapshot()).toMatchObject({
    shown: null,
    current: null,
    updating: true,
  });
  session.commit();
  await asked[0]!.reply(said("two_lines"));
  expect(session.snapshot().current).toBe(answer("two_lines"));
  expect(session.snapshot().digest).toBe(answer("two_lines").input_digest);
  expect(session.snapshot().updating).toBe(false);

  // An edit leaves the last answer on show, and no longer current.
  session.want(draftB);
  expect(session.snapshot()).toMatchObject({
    shown: answer("two_lines"),
    current: null,
    digest: null,
    updating: true,
  });
  session.commit();
  await asked[1]!.reply(said("rate_in_force_2023"));
  expect(session.snapshot().current).toBe(answer("rate_in_force_2023"));

  // Back to the draft already asked: its earlier answer was replaced.
  session.want(draftA);
  expect(session.snapshot().current).toBeNull();
});

test("one request is in flight, the latest wins, and a stale answer is dropped", async () => {
  const { asked, session } = ledger();
  session.want(draftA);
  session.commit();
  session.want(draftB);
  session.commit();
  expect(asked).toHaveLength(1);
  await asked[0]!.reply(said("two_lines"));
  // The overtaken answer says nothing, not even as the one on show.
  expect(session.snapshot()).toMatchObject({ shown: null, current: null });
  expect(asked.map(({ request }) => request)).toEqual([draftA, draftB]);
  await asked[1]!.reply(said("rate_in_force_2023"));
  expect(session.snapshot().current).toBe(answer("rate_in_force_2023"));
});

test("typing rests before anything is asked", async () => {
  const asked: InvoicePreviewRequest[] = [];
  const session = new InvoicePreviewSession(async (request) => {
    asked.push(request);
    return said("bare_2026");
  }, 5);
  session.want(draftA);
  session.want(draftB);
  expect(asked).toEqual([]);
  await expect.poll(() => session.snapshot().current).toBe(answer("bare_2026"));
  expect(asked).toEqual([draftB]);
});

test("an unavailable ledger leaves no figure, asks again on an edit or a retry, and is never unknown", async () => {
  const { asked, session } = ledger();
  session.want(draftA);
  session.commit();
  await asked[0]!.reply(said("two_lines"));
  session.want(draftB);
  session.commit();
  await asked[1]!.reply({ kind: "failed" });
  // Nothing cached survives it: no figure and no rate slot.
  expect(session.snapshot()).toEqual({
    shown: null,
    current: null,
    digest: null,
    updating: false,
    failed: true,
  });
  // The same draft is not asked about again by itself.
  session.want(draftB);
  session.commit();
  expect(asked).toHaveLength(2);
  session.retry();
  expect(session.snapshot()).toMatchObject({ failed: false, updating: true });
  expect(asked).toHaveLength(3);
  await asked[2]!.reply({ kind: "failed" });
  // An edit asks again.
  session.want(draftA);
  session.commit();
  expect(asked).toHaveLength(4);
  await asked[3]!.reply(said("two_lines"));
  expect(session.snapshot()).toMatchObject({
    current: answer("two_lines"),
    failed: false,
  });
});

test("a ledger call that throws is the same failure", async () => {
  const session = new InvoicePreviewSession(
    () => Promise.reject(new Error()),
    0,
  );
  session.want(draftA);
  session.commit();
  await expect.poll(() => session.snapshot().failed).toBe(true);
});

// ---- What each answer lets through -----------------------------------------------

test("the draft goes to the ledger as typed, blank fields null", () => {
  const { preview, problems } = readDraft(filled(), CORRECTIVE);
  expect(problems).toEqual({});
  expect(preview).toMatchObject(
    recorded.two_lines!.request as Record<string, unknown>,
  );
  expect(preview.lines?.map(({ key }) => key)).toEqual(["line-1", "line-2"]);
  expect(preview.printed_total).toBeNull();
  // A line nobody typed on is left out.
  const opened = emptyDraft("line-1", SERVED.defaultClass);
  expect(readDraft(opened, CORRECTIVE).preview.lines).toEqual([]);
  expect(readDraft(opened, CORRECTIVE).preview.counterparty_country).toBeNull();
});

test("an add carries the answer's figures, and only with an answer to this very draft", () => {
  const draft = filled();
  expect(checked(draft, null).request).toBeNull();
  const check = checked(draft, "two_lines");
  expect(check.invoiceId).toBe(answer("two_lines").invoice_id);
  expect(check.invariants).toEqual({
    counterparty: true,
    country: true,
    line: true,
    totals: true,
  });
  expect(check.request).toEqual({
    kind: "issued",
    counterparty_name: "Norte Digital S. Coop.",
    counterparty_tax_id: RECORDED_TAX_ID,
    counterparty_country: "ES",
    series: "F",
    invoice_number: `F-${fixtureYear}-021`,
    issued_at: fixtureDay(10, 23),
    currency: "EUR",
    notes: "",
    invoice_class: "ORDINARIA",
    lines: [
      {
        description: "Diseño de marca",
        quantity: { decimal: "1" },
        unit_price: { decimal: "550" },
        subtotal: { decimal: "550.00" },
        iva_rate: "RATE_21",
        iva_amount: { decimal: "115.50" },
      },
      {
        description: "Piezas gráficas",
        quantity: { decimal: "2" },
        unit_price: { decimal: "275" },
        subtotal: { decimal: "550.00" },
        iva_rate: "RATE_21",
        iva_amount: { decimal: "115.50" },
      },
    ],
  });
});

test("a figure typed badly keeps the add back even if an answer accepts", () => {
  const check = checked(filled({}, { quantity: "1.500" }), "two_lines");
  expect(check.request).toBeNull();
  expect(check.problems["line:line-1:quantity"]).toMatchObject({
    kind: "grammar",
    refusal: { key: "ambiguous_grouping" },
  });
});

test("nothing is assumed: the ledger names what a bare draft lacks", () => {
  const check = checked(emptyDraft("l1", SERVED.defaultClass), "bare_2026");
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

test("a stated IVA within the backend's cent is sent as stated", () => {
  const draft = filled({}, { statedIva: "115.51" });
  expect(readDraft(draft, CORRECTIVE).preview.lines?.[0]?.iva_amount).toEqual({
    decimal: "115.51",
  });
  const check = checked(draft, "stated_iva_within");
  expect(check.problems).toEqual({});
  expect(check.request?.lines?.[0]?.iva_amount).toEqual({ decimal: "115.51" });
});

test("a stated IVA the backend refuses stays on its own field", () => {
  const check = checked(
    filled({}, { statedIva: "115.60" }),
    "stated_iva_refused",
  );
  expect(check.request).toBeNull();
  expect(check.problems["line:line-1:statedIva"]).toMatchObject({
    kind: "finding",
    finding: { code: "line_iva_mismatch" },
  });
});

test("a stated subtotal is accepted and refused by the served answer alone", () => {
  const within = checked(
    filled({}, { statedSubtotal: "550.01" }),
    "stated_subtotal_within",
  );
  expect(within.request?.lines?.[0]?.subtotal).toEqual({ decimal: "550.01" });
  const refused = checked(
    filled({}, { statedSubtotal: "550.50" }),
    "stated_subtotal_refused",
  );
  expect(refused.request).toBeNull();
  expect(refused.problems["line:line-1:statedSubtotal"]).toMatchObject({
    kind: "finding",
  });
});

test("a printed total that differs warns and blocks nothing", () => {
  const check = checked(filled({ printedTotal: "1330.99" }), "printed_differs");
  expect(check.findings.warnings.printed?.code).toBe("printed_total_differs");
  expect(check.problems.printed).toBeUndefined();
  expect(check.invariants.totals).toBe(true);
  expect(check.request).not.toBeNull();
});

test("the retención is the backend's to judge, on its own fields", () => {
  const typed = filled({ retentionRate: "15", retentionAmount: "165" });
  const fine = checked(typed, "retention_15");
  expect(fine.request?.retention_rate).toEqual({ decimal: "0.15" });
  expect(fine.request?.retention_amount).toEqual({ decimal: "165" });
  expect(
    checked(filled({ retentionRate: "15" }), "retention_rate_alone").problems
      .retention_rate,
  ).toMatchObject({
    finding: { code: "retention_rate_without_amount" },
  });
  const differs = checked(
    filled({ retentionRate: "15", retentionAmount: "160" }),
    "retention_differs",
  );
  expect(differs.request).toBeNull();
  expect(differs.problems.retention_rate).toMatchObject({
    finding: { code: "retention_amount_mismatch" },
  });
  const above = checked(
    filled({ retentionRate: "15", retentionAmount: "1200" }),
    "retention_above_base",
  );
  expect(above.problems.retention_amount).toMatchObject({
    finding: { code: "retention_amount_above_base" },
  });
  expect(
    checked(filled({ recargo: "231.01" }), "recargo_above_iva").problems
      .recargo,
  ).toMatchObject({ finding: { code: "recargo_above_iva_total" } });
});

test("a date that strands a rate is a finding on that line", () => {
  const check = checked(filled({}, { rate: "RATE_5" }), "rate_not_in_force");
  expect(check.request).toBeNull();
  expect(check.problems["line:line-1:rate"]).toMatchObject({
    kind: "finding",
    finding: { code: "line_rate_not_in_force" },
  });
  const slot = (name: string, token: string) =>
    answer(name).rate_slots.find(({ slot }) => slot === token)?.in_force;
  expect(slot("rate_not_in_force", "RATE_5")).toBe(false);
  expect(slot("rate_in_force_2023", "RATE_5")).toBe(true);
});

test("before the registry's rates, the nearest rates are served and the projection is a warning", () => {
  const check = checked(
    filled({ issuedAt: `${servedSupport.floor - 2}-12-31` }),
    "before_registry",
  );
  expect(answer("before_registry").rate_slots.length).toBeGreaterThan(0);
  expect(check.request).not.toBeNull();
  expect(check.findings.general.map(({ code }) => code)).toEqual([
    "rate_date_projected",
  ]);
});

test("a document rule shows the ledger's own finding on its field, and waits to be asked", () => {
  const check = checked(filled({ taxId: "" }), "no_tax_id");
  expect(check.request).toBeNull();
  expect(check.refusedUnsaid).toBe(false);
  expect(check.problems.counterparty_tax_id).toMatchObject({
    kind: "finding",
    quiet: true,
    finding: {
      code: "counterparty_tax_id_required",
      label_key:
        "application.invoices.figures_preview.rule_finding.counterparty_tax_id_required",
    },
  });
  expect(
    checked(filled({ retentionRate: "15" }), "retention_rate_alone")
      .refusedUnsaid,
  ).toBe(false);
});

test("a category that mandates the tax id, a bad checksum and the lease rules come from the ledger", () => {
  const code = (name: string, draft: InvoiceDraft, place: string) => {
    const problem = checked(draft, name).problems[place];
    return problem?.kind === "finding" ? problem.finding.code : null;
  };
  expect(
    code(
      "tax_id_required_by_category",
      filled({ taxId: "", invoiceClass: "SIMPLIFICADA" }),
      "counterparty_tax_id",
    ),
  ).toBe("counterparty_tax_id_required_by_category");
  expect(
    code(
      "tax_id_bad_checksum",
      filled({ taxId: "B00000282" }),
      "counterparty_tax_id",
    ),
  ).toBe("counterparty_tax_id_invalid");
  const leased = { lease: true, situacion: "1", referencia: "A".repeat(26) };
  // The form no longer holds the number: 26 characters reach the ledger.
  expect(
    readDraft(filled(leased), CORRECTIVE).problems.referencia,
  ).toBeUndefined();
  expect(code("lease_reference_too_long", filled(leased), "referencia")).toBe(
    "lease_reference_too_long",
  );
  expect(answer("lease_reference_too_long").rule_findings[0]!.values).toEqual([
    { key: "limit", value: "25" },
  ]);
  expect(
    code(
      "lease_reference_abroad",
      filled({ lease: true, situacion: "4", referencia: "REF" }),
      "referencia",
    ),
  ).toBe("lease_reference_not_allowed");
});

test("a rectificativa hears both of its rules from the ledger", () => {
  const check = checked(
    filled({ invoiceClass: "RECTIFICATIVA", series: "" }),
    "rectificativa_incomplete",
  );
  expect(check.request).toBeNull();
  expect(check.problems.series).toMatchObject({
    finding: { code: "series_required_for_rectificativa" },
  });
  expect(check.problems.rectifies_invoice_number).toMatchObject({
    finding: { code: "rectified_invoice_required" },
  });
});

test("a refusal nobody can place is still said to be unsaid", () => {
  const silent = {
    ...answer("no_tax_id"),
    rule_findings: [],
  };
  const draft = filled({ taxId: "" });
  expect(
    checkDraft(draft, readDraft(draft, CORRECTIVE), silent).refusedUnsaid,
  ).toBe(true);
});

test("a finding is worded by its served key with its served values", () => {
  const words: { key: string; values?: Record<string, string | number> }[] = [];
  const t = Object.assign(
    (key: string, values?: Record<string, string | number>) => {
      words.push({ key, values });
      return key;
    },
    { locale: "en" },
  );
  const refused = answer("rate_not_in_force");
  findingText(t, refused.findings[0]!, refused.rate_slots);
  expect(words.at(-1)?.key).toBe(refused.findings[0]!.label_key);
  expect(words.at(-1)?.values?.on_date).toContain(String(fixtureYear));
  const differs = answer("printed_differs");
  findingText(t, differs.findings[0]!, differs.rate_slots);
  expect(words.at(-1)?.values).toEqual({
    computed: "1,331.00",
    printed: "1,330.99",
  });
});

test("a retención rate is read as points and reaches the wire as a fraction", () => {
  const wire = (retentionRate: string) =>
    readDraft(filled({ retentionRate }), CORRECTIVE).preview.retention_rate
      ?.decimal;
  expect(wire("15")).toBe("0.15");
  expect(wire("0.5")).toBe("0.005");
  expect(wire("0.5%")).toBe("0.005");
  // What a Spanish-language window hands over for `0,5%`: the percent editor
  // takes the sign off and the language's own marks are read to a point.
  const typed = readLocaleDecimal("es", "0,5");
  expect(typed).toBe("0.5");
  expect(wire(typed ?? "")).toBe("0.005");
  expect(
    readDraft(filled({ retentionRate: "150" }), CORRECTIVE).problems
      .retention_rate,
  ).toMatchObject({ refusal: { key: "percent_above_100" } });
});

test("the next number follows the highest in its series, class and year", () => {
  const catalogue = [
    invoice({
      invoice_id: "1".repeat(64),
      invoice_number: `F-${fixtureYear}-018`,
      issued_at: fixtureDay(9, 12),
    }),
    invoice({
      invoice_id: "2".repeat(64),
      invoice_number: `F-${fixtureYear}-020`,
      issued_at: fixtureDay(10, 10),
    }),
    invoice({
      invoice_id: "3".repeat(64),
      invoice_number: `F-${fixtureYear - 1}-099`,
      issued_at: fixtureDay(12, 18, -1),
    }),
    ...[`${fixtureYear}-007`, `${fixtureYear}-031`, `${fixtureYear}-009`].map(
      (number, at) =>
        invoice({
          invoice_id: String(4 + at).repeat(64),
          invoice_number: number,
          series: String(fixtureYear),
          issued_at: fixtureDay(5, 1),
        }),
    ),
    invoice({
      invoice_id: "8".repeat(64),
      invoice_number: `T-${fixtureYear}-0007`,
      series: "T",
      invoice_class: "SIMPLIFICADA",
    }),
    invoice({
      invoice_id: "9".repeat(64),
      invoice_number: `R-${fixtureYear}-02`,
      series: "R",
      invoice_class: "RECTIFICATIVA",
    }),
    invoice({
      invoice_id: "c".repeat(64),
      kind: "received",
      invoice_number: `F-${fixtureYear}-500`,
    }),
  ];
  // The numbers are counted within the calendar year the first invoice was issued in.
  const issuedYear = fixtureYear;
  const ask = (
    series: string,
    invoiceClass: "ORDINARIA" | "SIMPLIFICADA" | "RECTIFICATIVA" = "ORDINARIA",
    year = issuedYear,
  ) =>
    suggestNumber(catalogue, {
      kind: "issued",
      invoiceClass,
      correctiveClass: CORRECTIVE,
      series,
      year,
    });
  expect(ask("F")).toEqual({ series: "F", number: `F-${fixtureYear}-021` });
  // With no series typed, the class's most used series that year.
  expect(ask("")).toEqual({
    series: String(fixtureYear),
    number: `${fixtureYear}-032`,
  });
  expect(ask("", "SIMPLIFICADA")).toEqual({
    series: "T",
    number: `T-${fixtureYear}-0008`,
  });
  expect(ask("", "RECTIFICATIVA")).toBeNull();
  expect(ask("R", "RECTIFICATIVA")).toEqual({
    series: "R",
    number: `R-${fixtureYear}-03`,
  });
  expect(ask("F", "ORDINARIA", issuedYear - 1)).toEqual({
    series: "F",
    number: `F-${fixtureYear - 1}-100`,
  });
  // Nothing to follow: no suggestion is made up.
  expect(ask("Z")).toBeNull();
  expect(
    suggestNumber(catalogue, {
      kind: "received",
      invoiceClass: "ORDINARIA",
      correctiveClass: CORRECTIVE,
      series: "F",
      year: issuedYear,
    }),
  ).toBeNull();
});

test("a stored rate finer than a person types stands unsent until it is retyped", () => {
  const stored = invoice({
    retention_rate: { decimal: "0.1234567" },
    retention_amount: { decimal: "123.46" },
  });
  const draft = correctionOf(stored);
  expect(draft.retentionRate).toBe("12.34567");
  const kept = checkCorrection(
    stored,
    { ...draft, notes: "Cobrada" },
    null,
    null,
  );
  expect(kept.problems.retention_rate).toBeUndefined();
  expect(kept.request?.patch.fields).toEqual(["notes"]);
  expect(correctionPreview(stored, draft, null).retention_rate).toEqual({
    decimal: "0.1234567",
  });
  // Retyped, it is what the person typed, under the same limit as any other.
  const retyped = checkCorrection(
    stored,
    { ...draft, retentionRate: "12.34568" },
    null,
    null,
  );
  expect(retyped.problems.retention_rate).toBeDefined();
  expect(
    checkCorrection(stored, { ...draft, retentionRate: "12" }, null, null)
      .problems.retention_rate,
  ).toBeUndefined();
});

test("a stored rate that points write as 12.345 is held longer, so no language reads it as thousands", () => {
  const stored = invoice({
    retention_rate: { decimal: "0.12345" },
    retention_amount: { decimal: "123.45" },
  });
  const draft = correctionOf(stored);
  // `12.345` alone is a thousands run in Spanish; the held spelling is not.
  expect(draft.retentionRate).toBe("12.3450");
  expect(draft.retentionAmount).toBe("123.45");
  expect(checkCorrection(stored, draft, null, CORRECTIVE)).toMatchObject({
    changed: [],
    problems: {},
    request: null,
  });
});

test("a correction sends only the changed fields the update accepts", () => {
  const stored = invoice({
    retention_rate: { decimal: "0.15" },
    retention_amount: { decimal: "150.00" },
    operation_date: fixtureDay(3, 1),
    operation_date_role: "OPERATION_PERFORMED",
  });
  const draft = correctionOf(stored);
  expect(draft.retentionRate).toBe("15");
  expect(checkCorrection(stored, draft, null, CORRECTIVE)).toMatchObject({
    changed: [],
    request: null,
  });
  const paid = checkCorrection(
    stored,
    {
      ...draft,
      paymentStatus: "PAID",
      notes: "Cobrada",
    },
    null,
    CORRECTIVE,
  );
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
  // Leaving the rectificativa class takes its number away, once the ledger
  // has answered the change.
  const rectified = invoice({
    invoice_class: "RECTIFICATIVA",
    rectifies_invoice_number: `F-${fixtureYear}-001`,
  });
  expect(
    checkCorrection(
      rectified,
      {
        ...correctionOf(rectified),
        invoiceClass: "ORDINARIA",
      },
      answer("correction_no_retention"),
      CORRECTIVE,
    ).request?.patch,
  ).toEqual({
    values: { invoice_class: "ORDINARIA", rectifies_invoice_number: null },
    fields: ["invoice_class", "rectifies_invoice_number"],
  });
  expect(
    checkCorrection(stored, { ...draft, paymentId: "abc" }, null, CORRECTIVE)
      .problems.payment_id,
  ).toEqual({
    kind: "rule",
    rule: "payment_id_shape",
  });
});

test("a stored date, series and rectified number take the ledger's verdict", () => {
  const dated = invoice({
    operation_date: fixtureDay(3, 1),
    operation_date_role: "OPERATION_PERFORMED",
  });
  const taken = checkCorrection(
    dated,
    { ...correctionOf(dated), operationDate: "" },
    answer("correction_date_taken_away"),
    CORRECTIVE,
  );
  expect(taken.request).toBeNull();
  expect(taken.problems.operation_date).toMatchObject({
    finding: { code: "operation_date_role_mismatch" },
  });
  const plain = invoice();
  const added = checkCorrection(
    plain,
    { ...correctionOf(plain), operationDate: fixtureDay(3, 1) },
    answer("correction_date_added"),
    CORRECTIVE,
  );
  expect(added.request).toBeNull();
  expect(added.problems.operation_date).toMatchObject({
    finding: { code: "operation_date_role_mismatch" },
  });
  const rectificativa = checkCorrection(
    plain,
    { ...correctionOf(plain), invoiceClass: "RECTIFICATIVA", series: "" },
    answer("correction_rectificativa_incomplete"),
    CORRECTIVE,
  );
  expect(rectificativa.request).toBeNull();
  expect(rectificativa.problems.series).toMatchObject({
    finding: { code: "series_required_for_rectificativa" },
  });
  expect(rectificativa.problems.rectifies_invoice_number).toMatchObject({
    finding: { code: "rectified_invoice_required" },
  });
  // Neither is decided here: with no answer the change only waits.
  const waiting = checkCorrection(
    plain,
    { ...correctionOf(plain), invoiceClass: "RECTIFICATIVA", series: "" },
    null,
    CORRECTIVE,
  );
  expect(waiting.awaitingAnswer).toBe(true);
  expect(waiting.problems.series).toBeUndefined();
});

test("a correction is asked about with the stored invoice it restates, and its answer says what is left to pay", () => {
  const stored = invoice({
    counterparty_tax_id: RECORDED_TAX_ID,
    base_total: { decimal: "1000" },
  });
  expect(
    correctionPreview(
      stored,
      {
        ...correctionOf(stored),
        retentionRate: "7",
        retentionAmount: "70",
      },
      CORRECTIVE,
    ),
  ).toMatchObject(
    recorded.correction_rate_7!.request as Record<string, unknown>,
  );
  // 1000 x 7 % = 70 withheld, so 1210.00 - 70 = 1140.00 is left to pay.
  const answered = answer("correction_rate_7");
  expect(answered.verdict_scope).toBe("correction_facts");
  expect(answered.totals.net_of_retention).toEqual({ decimal: "1140.00" });
  expect(answer("correction_no_retention").totals.net_of_retention).toEqual({
    decimal: "1210.00",
  });
});

test("a changed retención waits for the ledger's answer and takes its verdict", () => {
  const stored = invoice({
    counterparty_tax_id: RECORDED_TAX_ID,
    base_total: { decimal: "1000" },
    retention_rate: { decimal: "0.15" },
    retention_amount: { decimal: "150" },
  });
  const seven = {
    ...correctionOf(stored),
    retentionRate: "7",
    retentionAmount: "70",
  };
  expect(correctionPreview(stored, seven, CORRECTIVE)).toMatchObject(
    recorded.correction_rate_7!.request as Record<string, unknown>,
  );
  const waiting = checkCorrection(stored, seven, null, CORRECTIVE);
  expect(waiting.awaitingAnswer).toBe(true);
  expect(waiting.request).toBeNull();
  const answered = checkCorrection(
    stored,
    seven,
    answer("correction_rate_7"),
    CORRECTIVE,
  );
  expect(answered.request?.patch.values).toEqual({
    retention_rate: { decimal: "0.07" },
    retention_amount: { decimal: "70" },
  });
  const differs = checkCorrection(
    stored,
    { ...seven, retentionAmount: "60" },
    answer("correction_rate_differs"),
    CORRECTIVE,
  );
  expect(differs.request).toBeNull();
  expect(differs.problems.retention_rate).toMatchObject({
    finding: { code: "retention_amount_mismatch" },
  });
  // A read that failed holds back only a change the ledger judges.
  expect(
    checkCorrection(
      stored,
      { ...correctionOf(stored), notes: "Cobrada" },
      null,
      CORRECTIVE,
    ).request,
  ).not.toBeNull();
});

test("the catalogue filters by kind, class, payment, links, period and words", () => {
  const catalogue = [
    invoice({
      invoice_id: "1".repeat(64),
      invoice_number: `F-${fixtureYear}-001`,
      issued_at: fixtureDay(2, 1),
    }),
    invoice({
      invoice_id: "2".repeat(64),
      kind: "received",
      invoice_number: "A-1093",
      counterparty_name: "Papelería Trazo",
      issued_at: fixtureDay(10, 14),
      payment_status: "CANCELLED",
      grand_total: { decimal: "93.17" },
    }),
    invoice({
      invoice_id: "3".repeat(64),
      invoice_number: `F-${fixtureYear}-002`,
      issued_at: fixtureDay(8, 1),
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
  ).toEqual([`F-${fixtureYear}-001`, "A-1093"]);
  expect(
    ids(filterCatalogue(catalogue, { ...NO_FILTER, payment: "CANCELLED" })),
  ).toEqual(["A-1093"]);
  // A period filters by the days the backend served for it, and keeps nothing
  // while they are not served.
  const third = { year: fixtureYear, code: "3T" } as const;
  expect(
    ids(filterCatalogue(catalogue, { ...NO_FILTER, period: third })),
  ).toEqual([]);
  holdRecordedPeriods("en");
  try {
    expect(
      ids(filterCatalogue(catalogue, { ...NO_FILTER, period: third })),
    ).toEqual([`F-${fixtureYear}-002`]);
  } finally {
    holdLedgerPeriods(null, null);
  }
  expect(
    ids(
      filterCatalogue(catalogue, { ...NO_FILTER, search: "papeleria 93,17" }),
    ),
  ).toEqual(["A-1093"]);
  expect(
    ids(sortCatalogue(catalogue, { key: "total", direction: "asc" })),
  ).toEqual(["A-1093", `F-${fixtureYear}-002`, `F-${fixtureYear}-001`]);
  expect(
    ids(sortCatalogue(catalogue, { key: "date", direction: "desc" })),
  ).toEqual(["A-1093", `F-${fixtureYear}-002`, `F-${fixtureYear}-001`]);
});

test("a payment id is read against the shape the ledger serves, and not at all while it serves none", () => {
  const stored = invoice({});
  const draft = correctionOf(stored);
  const id = "ab".repeat(32);
  expect(
    checkCorrection(
      stored,
      { ...draft, paymentId: id.toUpperCase() },
      null,
      CORRECTIVE,
    ).request?.patch.values.payment_id,
  ).toBe(id);
  expect(isPaymentId("ab".repeat(31))).toBe(false);
  try {
    holdLedgerLimits(null);
    expect(isPaymentId(id)).toBeNull();
    expect(
      checkCorrection(stored, { ...draft, paymentId: id }, null, CORRECTIVE)
        .problems.payment_id,
    ).toEqual({
      kind: "grammar",
      refusal: { key: "limits_unavailable", raw: id },
    });
  } finally {
    holdLedgerLimits(servedLimits);
  }
});
