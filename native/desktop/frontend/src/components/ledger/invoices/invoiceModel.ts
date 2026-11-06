// What the Invoices section reads from what the person typed before it asks
// the ledger anything, and the request an add or a correction sends. Text
// stays as typed and is only checked to be well formed. No figure, rate or
// tax rule is worked out here: every one comes from the ledger's preview, and
// an add sends the figures of the answer to the very draft on the page.

import type {
  CatalogueInvoice,
  InvoiceAddLine,
  InvoiceAddRequest,
  InvoiceKind,
  InvoicePreviewFinding,
  InvoicePreviewLine,
  InvoicePreviewRateSlot,
  InvoicePreviewRequest,
  InvoicePreviewResult,
  InvoiceUpdateRequest,
  InvoiceUpdateValues,
} from "../../../shell/ledgerInvoiceOperations";
import type { PublicDecimal } from "../../../shell/ledger";
import {
  INVOICE_UPDATE_FIELDS,
  isCorrectionJudged,
  type InvoiceUpdateField,
  type PaymentStatus,
} from "../../../shell/ledgerContract";
import {
  QUANTITY_RULE,
  TAX_AMOUNT_RULE,
  UNIT_PRICE_RULE,
  canonicalDecimal,
  compareDecimal,
  parseDecimal,
  parseIsoDate,
  parseLine,
  parsePercent,
  type DecimalRule,
  type GrammarRefusal,
  type LedgerPeriod,
} from "../../../shell/ledgerGrammar";
import { textLimit } from "../../../shell/ledgerLimits";
import { periodBounds } from "../../../shell/ledgerPeriods";
import { heldDecimal } from "../../../shared/numbers";
import { ledgerLimits } from "../../../shell/ledgerLimits";

// ---- Vocabularies -----------------------------------------------------------

/** An invoice class as the registry names it; the ledger serves which. */
export type InvoiceClass = string;

// ---- Lines -------------------------------------------------------------------

/** One line as typed. `rate` is a slot, or empty until one is chosen. A stated
 * figure is what the document prints, and stays blank when it prints none. */
export type LineDraft = {
  key: string;
  description: string;
  quantity: string;
  unitPrice: string;
  rate: string;
  category: string;
  statedSubtotal: string;
  statedIva: string;
};

export const emptyLine = (key: string): LineDraft => ({
  key,
  description: "",
  quantity: "1",
  unitPrice: "",
  rate: "",
  category: "",
  statedSubtotal: "",
  statedIva: "",
});

/** Why a value was not taken: the grammar's refusal, a missing fact, a rule,
 * or what the ledger's preview found. */
export type Problem =
  | { kind: "grammar"; refusal: GrammarRefusal }
  | { kind: "missing" }
  | { kind: "rule"; rule: RuleProblem; values?: Record<string, string> }
  | {
      kind: "finding";
      finding: InvoicePreviewFinding;
      slots: readonly InvoicePreviewRateSlot[];
      /** A document rule waits for the field to be left or the add to be
       * tried, so a form being filled in is not told off for what it lacks. */
      quiet?: boolean;
    };
export type RuleProblem =
  | "choose_kind"
  | "country_letters"
  | "currency_letters"
  | "choose_rate"
  | "no_line"
  | "payment_id_shape";

const grammar = (refusal: GrammarRefusal): Problem => ({
  kind: "grammar",
  refusal,
});
const decimal = (value: string): PublicDecimal => ({ decimal: value });
const blankOr = (value: string) => (value === "" ? null : value);

/** A decimal field: its value on the wire, or what keeps it off. */
function decimalField(
  raw: string,
  rule: DecimalRule,
): { value: PublicDecimal | null; problem: Problem | null } {
  const parsed = parseDecimal(raw, rule);
  if (parsed.kind === "refused")
    return { value: null, problem: grammar(parsed.refusal) };
  return {
    value: parsed.kind === "value" ? decimal(parsed.value) : null,
    problem: null,
  };
}

/** A one-line text field: its value, or its problem. */
function textField(
  raw: string,
  max?: number | null,
): { value: string | null; problem: Problem | null } {
  const parsed = parseLine(raw, max);
  if (parsed.kind === "refused")
    return { value: null, problem: grammar(parsed.refusal) };
  return {
    value: parsed.kind === "value" ? parsed.value : null,
    problem: null,
  };
}

/** Something was typed on it beyond the quantity it opens with. A line nobody
 * typed on is left out of the invoice. */
export const lineEntered = (line: LineDraft) =>
  line.description.trim() !== "" ||
  line.unitPrice.trim() !== "" ||
  line.rate !== "" ||
  line.category !== "" ||
  line.statedSubtotal.trim() !== "" ||
  line.statedIva.trim() !== "" ||
  (line.quantity.trim() !== "" && line.quantity.trim() !== "1");

function readLine(
  line: LineDraft,
  received: boolean,
  problems: Record<string, Problem>,
): InvoicePreviewLine {
  const note = (field: string, problem: Problem | null) => {
    if (problem) problems[`line:${line.key}:${field}`] = problem;
  };
  const description = textField(line.description);
  note("description", description.problem);
  const quantity = decimalField(line.quantity, QUANTITY_RULE);
  note("quantity", quantity.problem);
  const price = decimalField(line.unitPrice, UNIT_PRICE_RULE);
  note("unitPrice", price.problem);
  const subtotal = decimalField(line.statedSubtotal, TAX_AMOUNT_RULE);
  note("statedSubtotal", subtotal.problem);
  const iva = decimalField(line.statedIva, TAX_AMOUNT_RULE);
  note("statedIva", iva.problem);
  return {
    key: line.key,
    description: description.value,
    quantity: quantity.value,
    unit_price: price.value,
    iva_rate: blankOr(line.rate),
    subtotal: subtotal.value,
    iva_amount: iva.value,
    spending_category_id: received ? blankOr(line.category) : null,
  };
}

// ---- What the preview found, by where it is shown -----------------------------

const INVOICE_PLACES: Record<string, string> = {
  recargo_amount: "recargo",
  printed_total: "printed",
  retention_rate: "retention_rate",
  retention_amount: "retention_amount",
};
/** Where a document rule's fields are shown. A figure finding that names a
 * date concerns the rates of that date, and is not the date's own problem. */
const RULE_PLACES: Record<string, string> = {
  counterparty_name: "counterparty_name",
  counterparty_tax_id: "counterparty_tax_id",
  counterparty_country: "counterparty_country",
  invoice_number: "invoice_number",
  currency: "currency",
  series: "series",
  rectifies_invoice_number: "rectifies_invoice_number",
  referencia_catastral: "referencia",
  situacion_inmueble: "situacion",
  operation_date: "operation_date",
  iva_category: "iva_category",
  invoice_class: "invoice_class",
};
const LINE_PLACES: Record<string, string> = {
  description: "description",
  quantity: "quantity",
  unit_price: "unitPrice",
  subtotal: "statedSubtotal",
  iva_amount: "statedIva",
  iva_rate: "rate",
};

/** The field a finding is shown on, if the form has one. */
function placeOf(
  finding: InvoicePreviewFinding,
  invoicePlaces: Record<string, string>,
): string | null {
  const places = finding.line_key ? LINE_PLACES : invoicePlaces;
  const field = finding.fields.find((name) => name in places);
  if (!field) return null;
  return finding.line_key
    ? `line:${finding.line_key}:${places[field]}`
    : places[field]!;
}

export type PlacedFindings = {
  /** Warnings by field: they inform, and never stop anything. */
  warnings: Record<string, InvoicePreviewFinding>;
  /** Findings with no field of their own. */
  general: InvoicePreviewFinding[];
};

/** Puts each finding on its field. A refusal becomes that field's problem,
 * unless the field already has one of its own. */
function placeFindings(
  answer: InvoicePreviewResult,
  problems: Record<string, Problem>,
): PlacedFindings {
  const placed: PlacedFindings = { warnings: {}, general: [] };
  for (const finding of answer.findings) {
    const place = placeOf(finding, INVOICE_PLACES);
    if (place === null) placed.general.push(finding);
    else if (finding.severity === "warning") placed.warnings[place] = finding;
    else if (problems[place]) placed.general.push(finding);
    else
      problems[place] = { kind: "finding", finding, slots: answer.rate_slots };
  }
  // A field already showing its own problem says enough: the rest of what the
  // rules found there follows once that is put right.
  for (const finding of answer.rule_findings) {
    const place = placeOf(finding, RULE_PLACES);
    if (place === null) placed.general.push(finding);
    else
      problems[place] ??= {
        kind: "finding",
        finding,
        slots: answer.rate_slots,
        quiet: true,
      };
  }
  return placed;
}

const refuses = (answer: InvoicePreviewResult) =>
  answer.findings.some((finding) => finding.severity === "refusal");

// ---- The new invoice -----------------------------------------------------------

/** A new invoice as typed. Nothing is assumed: no kind, country or currency
 * until the person gives one. */
export type InvoiceDraft = {
  kind: InvoiceKind | null;
  invoiceClass: InvoiceClass;
  series: string;
  number: string;
  issuedAt: string;
  operationDate: string;
  counterpartyName: string;
  taxId: string;
  country: string;
  currency: string;
  ivaCategory: string;
  operationType: string;
  rectifies: string;
  recargo: string;
  printedTotal: string;
  retentionRate: string;
  retentionAmount: string;
  lease: boolean;
  situacion: string;
  referencia: string;
  notes: string;
  lines: LineDraft[];
};

export const emptyDraft = (
  firstLine: string,
  defaultClass: string | null,
): InvoiceDraft => ({
  kind: null,
  invoiceClass: defaultClass ?? "",
  series: "",
  number: "",
  issuedAt: "",
  operationDate: "",
  counterpartyName: "",
  taxId: "",
  country: "",
  currency: "",
  ivaCategory: "",
  operationType: "",
  rectifies: "",
  recargo: "",
  printedTotal: "",
  retentionRate: "",
  retentionAmount: "",
  lease: false,
  situacion: "",
  referencia: "",
  notes: "",
  lines: [emptyLine(firstLine)],
});

/** The four facts every new invoice needs, named before anything is sent. */
export const CREATION_INVARIANTS = [
  "counterparty",
  "country",
  "line",
  "totals",
] as const;
export type CreationInvariant = (typeof CREATION_INVARIANTS)[number];

const COUNTRY = /^[A-Za-z]{2}$/;
const CURRENCY = /^[A-Za-z]{3}$/;

/** The retención rate a draft holds, read as points: the draft takes `15`,
 * `0.5` or `0.5%` as percentages, so a bare number is never taken for a
 * fraction. The value is the fraction the wire carries. */
export function retentionRate(text: string): ReturnType<typeof parsePercent> {
  const typed = text.trim();
  return parsePercent(typed === "" || typed.endsWith("%") ? text : `${typed}%`);
}

/** The two retención fields on the wire, and what keeps either off it. */
function readRetention(rateText: string, amountText: string) {
  const parsedRate = retentionRate(rateText);
  const amount = decimalField(amountText, TAX_AMOUNT_RULE);
  return {
    rate: parsedRate.kind === "value" ? decimal(parsedRate.value) : null,
    amount: amount.value,
    rateProblem:
      parsedRate.kind === "refused" ? grammar(parsedRate.refusal) : null,
    amountProblem: amount.problem,
  };
}

export type DraftReading = {
  /** What is typed badly, by field; a line's by `line:<key>:<field>`. */
  problems: Record<string, Problem>;
  /** The draft as the ledger is asked about it: a blank field is null. */
  preview: InvoicePreviewRequest;
};

/** The draft on the wire, with whatever is not well formed left blank. */
export function readDraft(
  draft: InvoiceDraft,
  correctiveClass: string | null,
): DraftReading {
  const problems: Record<string, Problem> = {};
  const note = (field: string, problem: Problem | null) => {
    if (problem) problems[field] = problem;
  };
  const received = draft.kind === "received";
  const lines = draft.lines
    .filter(lineEntered)
    .map((line) => readLine(line, received, problems));
  const recargo = decimalField(draft.recargo, TAX_AMOUNT_RULE);
  note("recargo", recargo.problem);
  const printed = decimalField(draft.printedTotal, TAX_AMOUNT_RULE);
  note("printed", printed.problem);
  const retention = readRetention(draft.retentionRate, draft.retentionAmount);
  note("retention_rate", retention.rateProblem);
  note("retention_amount", retention.amountProblem);
  const name = textField(
    draft.counterpartyName,
    textLimit("invoice_counterparty_name"),
  );
  note("counterparty_name", name.problem);
  const country = draft.country.trim();
  if (country !== "" && !COUNTRY.test(country))
    problems.counterparty_country = { kind: "rule", rule: "country_letters" };
  const currency = draft.currency.trim();
  if (currency !== "" && !CURRENCY.test(currency))
    problems.currency = { kind: "rule", rule: "currency_letters" };
  const number = textField(draft.number);
  note("invoice_number", number.problem);
  const issued = parseIsoDate(draft.issuedAt);
  if (issued.kind === "refused") problems.issued_at = grammar(issued.refusal);
  const operation = parseIsoDate(draft.operationDate);
  if (operation.kind === "refused")
    problems.operation_date = grammar(operation.refusal);
  const taxId = textField(draft.taxId);
  note("counterparty_tax_id", taxId.problem);
  const series = textField(draft.series);
  note("series", series.problem);
  const rectifies = textField(draft.rectifies);
  note("rectifies_invoice_number", rectifies.problem);
  const leased = draft.kind === "issued" && draft.lease;
  const referencia = textField(draft.referencia);
  if (leased) note("referencia", referencia.problem);
  return {
    problems,
    preview: {
      kind: draft.kind,
      invoice_class: draft.invoiceClass || null,
      series: series.value,
      invoice_number: number.value,
      issued_at: issued.kind === "value" ? issued.value : null,
      operation_date: operation.kind === "value" ? operation.value : null,
      counterparty_name: name.value,
      counterparty_tax_id: taxId.value,
      counterparty_country: COUNTRY.test(country)
        ? country.toUpperCase()
        : null,
      currency: CURRENCY.test(currency) ? currency.toUpperCase() : null,
      iva_category: blankOr(draft.ivaCategory),
      operation_type: blankOr(draft.operationType),
      rectifies_invoice_number:
        draft.invoiceClass === correctiveClass ? rectifies.value : null,
      recargo_amount: recargo.value,
      printed_total: printed.value,
      retention_rate: retention.rate,
      retention_amount: retention.amount,
      business_premises_lease: leased
        ? {
            situacion_inmueble: blankOr(draft.situacion),
            referencia_catastral: referencia.value,
          }
        : null,
      notes: draft.notes.trim(),
      lines,
    },
  };
}

export type DraftCheck = {
  /** Which of the four invariants hold now. */
  invariants: Record<CreationInvariant, boolean>;
  /** Field problems, by field; a line's by `line:<key>:<field>`. */
  problems: Record<string, Problem>;
  /** What the preview found that stops nothing or has no field. */
  findings: PlacedFindings;
  /** The ledger would refuse it and its findings do not say why. */
  refusedUnsaid: boolean;
  /** The request and the id its invoice will have, where the ledger's answer
   * to this very draft would accept it. */
  request: InvoiceAddRequest | null;
  invoiceId: string | null;
};

/** Where the ledger names a missing fact, on the field that lacks it. */
function placeMissing(
  answer: InvoicePreviewResult,
  problems: Record<string, Problem>,
): void {
  for (const name of answer.missing_fields) {
    const line = /^lines\.(.+)\.([a-z_]+)$/.exec(name);
    const place = line
      ? `line:${line[1]}:${LINE_PLACES[line[2]!] ?? line[2]}`
      : name;
    if (problems[place]) continue;
    if (name === "kind") problems.kind = { kind: "rule", rule: "choose_kind" };
    else if (name === "lines")
      problems.lines = { kind: "rule", rule: "no_line" };
    else if (line && line[2] === "iva_rate")
      problems[place] = { kind: "rule", rule: "choose_rate" };
    else problems[place] = { kind: "missing" };
  }
}

/** The add the ledger's answer allows: the document's own words with the
 * answer's figures. Null unless every figure is there. */
function addRequest(
  kind: InvoiceKind,
  preview: InvoicePreviewRequest,
  answer: InvoicePreviewResult,
): InvoiceAddRequest | null {
  const lines: InvoiceAddLine[] = [];
  for (const line of preview.lines ?? []) {
    const served = answer.lines.find((found) => found.key === line.key);
    const subtotal = served?.subtotal.submitted;
    const iva = served?.iva_amount.submitted;
    if (
      !subtotal ||
      !iva ||
      !line.description ||
      !line.quantity ||
      !line.unit_price ||
      !line.iva_rate
    )
      return null;
    lines.push({
      description: line.description,
      quantity: line.quantity,
      unit_price: line.unit_price,
      subtotal,
      iva_rate: line.iva_rate,
      iva_amount: iva,
      ...(line.spending_category_id
        ? { spending_category_id: line.spending_category_id }
        : {}),
    });
  }
  const {
    counterparty_name: name,
    counterparty_country: country,
    invoice_number: number,
    issued_at: issued,
    currency,
  } = preview;
  if (!name || !country || !number || !issued || !currency) return null;
  const { rate, amount } = answer.retention;
  const { recargo } = answer.totals;
  return {
    kind,
    counterparty_name: name,
    counterparty_tax_id: preview.counterparty_tax_id ?? null,
    counterparty_country: country,
    invoice_number: number,
    issued_at: issued,
    currency,
    notes: preview.notes ?? "",
    invoice_class: preview.invoice_class ?? null,
    lines,
    ...(preview.series ? { series: preview.series } : {}),
    ...(preview.operation_date
      ? { operation_date: preview.operation_date }
      : {}),
    ...(preview.iva_category ? { iva_category: preview.iva_category } : {}),
    ...(preview.operation_type
      ? { operation_type: preview.operation_type }
      : {}),
    ...(preview.rectifies_invoice_number
      ? { rectifies_invoice_number: preview.rectifies_invoice_number }
      : {}),
    ...(recargo ? { recargo_amount: recargo } : {}),
    ...(rate ? { retention_rate: rate } : {}),
    ...(amount ? { retention_amount: amount } : {}),
    ...(preview.business_premises_lease
      ? { business_premises_lease: preview.business_premises_lease }
      : {}),
  };
}

/** Everything the editor knows about a new invoice. `current` is the ledger's
 * answer to this very draft, or null while there is none: without it nothing
 * can be added. */
export function checkDraft(
  draft: InvoiceDraft,
  { problems: typed, preview }: DraftReading,
  current: InvoicePreviewResult | null,
): DraftCheck {
  const problems = { ...typed };
  let findings: PlacedFindings = { warnings: {}, general: [] };
  if (current) {
    findings = placeFindings(current, problems);
    placeMissing(current, problems);
  }
  const wellFormed = Object.keys(typed).length === 0;
  const lines = current
    ? current.missing_fields.every((name) => !name.startsWith("lines"))
    : false;
  const accepted = current?.verdict === "would_accept" ? current : null;
  const request =
    accepted && wellFormed && draft.kind !== null
      ? addRequest(draft.kind, preview, accepted)
      : null;
  return {
    invariants: {
      counterparty:
        preview.counterparty_name != null && !typed.counterparty_name,
      country: preview.counterparty_country != null,
      line: lines,
      totals:
        lines &&
        current !== null &&
        current.totals.total !== null &&
        !refuses(current),
    },
    problems,
    findings,
    refusedUnsaid:
      current !== null &&
      current.verdict === "would_refuse" &&
      !refuses(current) &&
      current.rule_findings.length === 0,
    request,
    invoiceId: request ? (accepted?.invoice_id ?? null) : null,
  };
}

// ---- The next number of a series ------------------------------------------------

export type NumberSuggestion = { series: string; number: string };

const SUFFIX = /^(.*?)(\d+)$/;

/**
 * The number that follows the highest one issued in a series in `year`:
 * the series typed, or with none typed the one most used for the invoice
 * class that year. The suffix keeps its zero padding. A rectificativa gets
 * no suggestion until its series is chosen, and a series with no number
 * that year gets none: there is nothing to follow.
 */
export function suggestNumber(
  invoices: readonly CatalogueInvoice[],
  want: {
    kind: InvoiceKind | null;
    invoiceClass: InvoiceClass;
    correctiveClass: string | null;
    series: string;
    year: number;
  },
): NumberSuggestion | null {
  if (want.kind !== "issued") return null;
  const typed = want.series.trim();
  if (!typed && want.invoiceClass === want.correctiveClass) return null;
  const pool = invoices.filter(
    (invoice) =>
      invoice.kind === "issued" &&
      invoice.invoice_class === want.invoiceClass &&
      invoice.issued_at.startsWith(`${String(want.year).padStart(4, "0")}-`),
  );
  let series = typed;
  if (!series) {
    const used = new Map<string, number>();
    for (const invoice of pool)
      if (invoice.series)
        used.set(invoice.series, (used.get(invoice.series) ?? 0) + 1);
    const ranked = [...used].sort(
      (left, right) => right[1] - left[1] || left[0].localeCompare(right[0]),
    );
    if (!ranked[0]) return null;
    series = ranked[0][0];
  }
  let best: { prefix: string; digits: string; value: bigint } | null = null;
  for (const invoice of pool) {
    if (invoice.series !== series) continue;
    const found = SUFFIX.exec(invoice.invoice_number);
    if (!found) continue;
    const value = BigInt(found[2]!);
    if (!best || value > best.value)
      best = { prefix: found[1]!, digits: found[2]!, value };
  }
  if (!best) return null;
  const next = (best.value + 1n).toString().padStart(best.digits.length, "0");
  return { series, number: `${best.prefix}${next}` };
}

// ---- Corrections ----------------------------------------------------------------

/** A stored invoice's correctable fields as the editor holds them. The
 * payment id is not shown by the catalogue: blank leaves it as it is. */
export type CorrectionDraft = {
  counterpartyName: string;
  country: string;
  notes: string;
  paymentStatus: PaymentStatus;
  ivaCategory: string;
  operationType: string;
  operationDate: string;
  retentionRate: string;
  retentionAmount: string;
  series: string;
  invoiceClass: string;
  rectifies: string;
  paymentId: string;
};

export function correctionOf(invoice: CatalogueInvoice): CorrectionDraft {
  const rate = invoice.retention_rate?.decimal ?? null;
  return {
    counterpartyName: invoice.counterparty_name,
    country: invoice.counterparty_country,
    notes: invoice.notes,
    paymentStatus: invoice.payment_status,
    ivaCategory: invoice.iva_category ?? "",
    operationType: invoice.operation_type ?? "",
    operationDate: invoice.operation_date ?? "",
    retentionRate: rate === null ? "" : heldDecimal(percentText(rate) ?? ""),
    retentionAmount: invoice.retention_amount
      ? heldDecimal(canonicalDecimal(invoice.retention_amount.decimal) ?? "")
      : "",
    series: invoice.series ?? "",
    invoiceClass: invoice.invoice_class,
    rectifies: invoice.rectifies_invoice_number ?? "",
    paymentId: "",
  };
}
/** A correction's retención. A stored rate finer than a person types is seeded
 * in full and stands as stored until retyped: it is neither refused nor sent. */
function correctionRetention(
  invoice: CatalogueInvoice,
  draft: CorrectionDraft,
) {
  const read = readRetention(draft.retentionRate, draft.retentionAmount);
  return invoice.retention_rate &&
    draft.retentionRate === correctionOf(invoice).retentionRate
    ? { ...read, rate: invoice.retention_rate, rateProblem: null }
    : read;
}

/** A stored fraction in the points the field is typed in. */
function percentText(fraction: string): string | null {
  const found = /^(\d+)(?:\.(\d+))?$/.exec(fraction);
  if (!found) return null;
  const decimals = found[2] ?? "";
  const digits = (BigInt(`${found[1]}${decimals}`) * 100n)
    .toString()
    .padStart(decimals.length + 1, "0");
  const whole = digits.slice(0, digits.length - decimals.length);
  const rest = digits.slice(digits.length - decimals.length);
  return canonicalDecimal(rest ? `${whole}.${rest}` : whole);
}

/** A correction as the ledger is asked about it: its lines are fixed, so the
 * stored base and total stand in for them, and `stored` says so. */
export function correctionPreview(
  invoice: CatalogueInvoice,
  draft: CorrectionDraft,
  correctiveClass: string | null,
): InvoicePreviewRequest {
  const operation = parseIsoDate(draft.operationDate);
  const retention = correctionRetention(invoice, draft);
  const country = draft.country.trim().toUpperCase();
  return {
    kind: invoice.kind,
    invoice_class: draft.invoiceClass,
    series: textField(draft.series).value,
    rectifies_invoice_number:
      draft.invoiceClass === correctiveClass
        ? textField(draft.rectifies).value
        : null,
    counterparty_tax_id: invoice.counterparty_tax_id,
    counterparty_country: COUNTRY.test(country) ? country : null,
    iva_category: blankOr(draft.ivaCategory),
    issued_at: invoice.issued_at,
    operation_date: operation.kind === "value" ? operation.value : null,
    base_total: invoice.base_total,
    retention_rate: retention.rate,
    retention_amount: retention.amount,
    stored: {
      invoice_id: invoice.invoice_id,
      grand_total: invoice.grand_total,
      operation_date_role: invoice.operation_date_role,
    },
  };
}

export type CorrectionCheck = {
  /** The fields whose value differs from the stored one. */
  changed: InvoiceUpdateField[];
  problems: Record<string, Problem>;
  findings: PlacedFindings;
  /** A change the ledger judges has no answer from it yet. */
  awaitingAnswer: boolean;
  request: InvoiceUpdateRequest | null;
};

/** Whether `text` has the shape of a payment id, as the ledger serves it; null
 * where it serves none. */
export const isPaymentId = (text: string): boolean | null => {
  const pattern = ledgerLimits()?.payment_id_pattern;
  return pattern === undefined ? null : new RegExp(pattern).test(text);
};

/** The correction a draft makes to `invoice`, field by field. Only the fields
 * the update accepts are ever sent, and only those that changed. A change
 * the ledger judges goes only once its answer, `current`, refuses nothing;
 * that answer covers the stated facts, and the update checks the whole record. */
export function checkCorrection(
  invoice: CatalogueInvoice,
  draft: CorrectionDraft,
  current: InvoicePreviewResult | null,
  correctiveClass: string | null,
): CorrectionCheck {
  const problems: Record<string, Problem> = {};
  const values: InvoiceUpdateValues = {};
  const changed: InvoiceUpdateField[] = [];
  const set = <F extends InvoiceUpdateField>(
    field: F,
    value: InvoiceUpdateValues[F],
  ) => {
    changed.push(field);
    values[field] = value;
  };
  const name = textField(
    draft.counterpartyName,
    textLimit("invoice_counterparty_name"),
  );
  if (name.problem) problems.counterparty_name = name.problem;
  else if (name.value === null)
    problems.counterparty_name = { kind: "missing" };
  else if (name.value !== invoice.counterparty_name)
    set("counterparty_name", name.value);
  const country = draft.country.trim().toUpperCase();
  if (!COUNTRY.test(country))
    problems.counterparty_country =
      country === ""
        ? { kind: "missing" }
        : { kind: "rule", rule: "country_letters" };
  else if (country !== invoice.counterparty_country)
    set("counterparty_country", country);
  // Notes are never cleared to nothing: an empty note is the empty text.
  if (draft.notes.trim() !== invoice.notes.trim())
    set("notes", draft.notes.trim());
  if (draft.paymentStatus !== invoice.payment_status)
    set("payment_status", draft.paymentStatus);
  if ((draft.ivaCategory || null) !== invoice.iva_category)
    set("iva_category", draft.ivaCategory || null);
  if ((draft.operationType || null) !== invoice.operation_type)
    set("operation_type", draft.operationType || null);
  const operation = parseIsoDate(draft.operationDate);
  if (operation.kind === "refused")
    problems.operation_date = grammar(operation.refusal);
  else {
    const next = operation.kind === "value" ? operation.value : null;
    if (next !== invoice.operation_date) set("operation_date", next);
  }
  const series = textField(draft.series);
  if (series.problem) problems.series = series.problem;
  else if (series.value !== invoice.series) set("series", series.value);
  if (draft.invoiceClass !== invoice.invoice_class)
    set("invoice_class", draft.invoiceClass);
  const rectifies = textField(draft.rectifies);
  const rectificativa = draft.invoiceClass === correctiveClass;
  const rectified = rectificativa ? rectifies.value : null;
  // Only a rectificativa names the invoice it rectifies: leaving that class
  // takes the number away.
  if (rectificativa && rectifies.problem)
    problems.rectifies_invoice_number = rectifies.problem;
  else if (rectified !== invoice.rectifies_invoice_number)
    set("rectifies_invoice_number", rectified);
  const retention = correctionRetention(invoice, draft);
  if (retention.rateProblem) problems.retention_rate = retention.rateProblem;
  if (retention.amountProblem)
    problems.retention_amount = retention.amountProblem;
  const sameNumber = (
    left: PublicDecimal | null,
    right: PublicDecimal | null,
  ) =>
    left === right ||
    (left !== null &&
      right !== null &&
      compareDecimal(left.decimal, right.decimal) === 0);
  const rateChanged =
    !retention.rateProblem &&
    !sameNumber(retention.rate, invoice.retention_rate);
  const amountChanged =
    !retention.amountProblem &&
    !sameNumber(retention.amount, invoice.retention_amount);
  if (rateChanged) set("retention_rate", retention.rate);
  if (amountChanged) set("retention_amount", retention.amount);
  const judged = changed.some(isCorrectionJudged);
  const findings: PlacedFindings =
    judged && current
      ? placeFindings(current, problems)
      : { warnings: {}, general: [] };
  const paymentId = draft.paymentId.trim().toLowerCase();
  if (paymentId !== "") {
    const shaped = isPaymentId(paymentId);
    if (shaped === null)
      problems.payment_id = grammar({
        key: "limits_unavailable",
        raw: paymentId,
      });
    else if (!shaped)
      problems.payment_id = { kind: "rule", rule: "payment_id_shape" };
    else set("payment_id", paymentId);
  }
  const ordered = INVOICE_UPDATE_FIELDS.filter((field) =>
    changed.includes(field),
  );
  const awaitingAnswer = judged && current === null;
  return {
    changed: ordered,
    problems,
    findings,
    awaitingAnswer,
    request:
      ordered.length > 0 &&
      Object.keys(problems).length === 0 &&
      findings.general.length === 0 &&
      !awaitingAnswer &&
      !(judged && current?.verdict === "would_refuse")
        ? {
            invoice_id: invoice.invoice_id,
            patch: { values, fields: ordered },
          }
        : null,
  };
}

/** Whether `invoice` now holds what `request` asked for: a correction read
 * back after its outcome was not seen. */
export function holdsCorrection(
  invoice: CatalogueInvoice,
  request: InvoiceUpdateRequest,
): boolean {
  const { values, fields } = request.patch;
  return fields.every((field) => {
    const wanted = values[field] ?? null;
    if (field === "payment_id") return true;
    const stored =
      (invoice as unknown as Record<string, unknown>)[field] ?? null;
    if (wanted !== null && typeof wanted === "object")
      return (
        stored !== null &&
        typeof stored === "object" &&
        compareDecimal(
          (stored as PublicDecimal).decimal,
          (wanted as PublicDecimal).decimal,
        ) === 0
      );
    return stored === wanted;
  });
}

// ---- The catalogue as the section shows it ----------------------------------------

export type CatalogueFilter = {
  kind: InvoiceKind | "all";
  search: string;
  invoiceClass: string;
  payment: string;
  unmatched: boolean;
  period: LedgerPeriod | null;
};
export const NO_FILTER: CatalogueFilter = {
  kind: "all",
  search: "",
  invoiceClass: "",
  payment: "",
  unmatched: false,
  period: null,
};

export const CATALOGUE_SORT_KEYS = [
  "kind",
  "number",
  "date",
  "operation_date",
  "counterparty",
  "tax_id",
  "country",
  "class",
  "base",
  "iva",
  "recargo",
  "retention",
  "total",
  "currency",
  "linked",
  "payment",
  "notes",
] as const;
export type CatalogueSortKey = (typeof CATALOGUE_SORT_KEYS)[number];
export type CatalogueSort = {
  key: CatalogueSortKey;
  direction: "asc" | "desc";
};

const fold = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();

/** An invoice's number as the catalogue writes it, with its series where
 * the number does not already start with it. */
export function seriesAndNumber(invoice: CatalogueInvoice): string {
  const series = invoice.series;
  return series && !invoice.invoice_number.startsWith(series)
    ? `${series} ${invoice.invoice_number}`
    : invoice.invoice_number;
}

/** The invoices `filter` keeps. Search words match separately, over the
 * number, series, counterparty, tax id and notes, and amounts written
 * either way. */
export function filterCatalogue(
  invoices: readonly CatalogueInvoice[],
  filter: CatalogueFilter,
): CatalogueInvoice[] {
  const span = filter.period ? periodBounds(filter.period) : null;
  // A period whose days are not served keeps nothing: it is not known to hold
  // any invoice, and no span is made up for it.
  if (filter.period && span === null) return [];
  const words = fold(filter.search).split(/\s+/).filter(Boolean);
  return invoices.filter((invoice) => {
    if (filter.kind !== "all" && invoice.kind !== filter.kind) return false;
    if (filter.invoiceClass && invoice.invoice_class !== filter.invoiceClass)
      return false;
    if (filter.payment && invoice.payment_status !== filter.payment)
      return false;
    if (filter.unmatched && invoice.linked_transaction_ids.length > 0)
      return false;
    if (span && (invoice.issued_at < span.from || invoice.issued_at > span.to))
      return false;
    if (words.length === 0) return true;
    const haystack = fold(
      [
        invoice.invoice_number,
        invoice.series ?? "",
        invoice.counterparty_name,
        invoice.counterparty_tax_id ?? "",
        invoice.notes,
        invoice.grand_total.decimal,
        invoice.base_total.decimal,
      ].join(" "),
    );
    return words.every((word) =>
      haystack.includes(/^\d+,\d+$/.test(word) ? word.replace(",", ".") : word),
    );
  });
}

function sortValue(
  invoice: CatalogueInvoice,
  key: CatalogueSortKey,
): string | number | null {
  switch (key) {
    case "kind":
      return invoice.kind;
    case "number":
      return seriesAndNumber(invoice);
    case "date":
      return invoice.issued_at;
    case "operation_date":
      return invoice.operation_date;
    case "counterparty":
      return fold(invoice.counterparty_name);
    case "tax_id":
      return invoice.counterparty_tax_id;
    case "country":
      return invoice.counterparty_country;
    case "class":
      return invoice.invoice_class;
    case "base":
      return invoice.base_total.decimal;
    case "iva":
      return invoice.iva_total.decimal;
    case "recargo":
      return invoice.recargo_amount?.decimal ?? null;
    case "retention":
      return invoice.retention_amount?.decimal ?? null;
    case "total":
      return invoice.grand_total.decimal;
    case "currency":
      return invoice.currency;
    case "linked":
      return invoice.linked_transaction_ids.length;
    case "payment":
      return invoice.payment_status;
    case "notes":
      return fold(invoice.notes);
  }
}
const DECIMAL_KEYS: ReadonlySet<CatalogueSortKey> = new Set([
  "base",
  "iva",
  "recargo",
  "retention",
  "total",
]);

/** The invoices in `sort`'s order. Empty values go last either way, and
 * ties keep the issue date, newest first, then the number. */
export function sortCatalogue(
  invoices: readonly CatalogueInvoice[],
  sort: CatalogueSort,
): CatalogueInvoice[] {
  const sign = sort.direction === "asc" ? 1 : -1;
  const compare = (left: CatalogueInvoice, right: CatalogueInvoice) => {
    const a = sortValue(left, sort.key);
    const b = sortValue(right, sort.key);
    if (a === null || b === null) return a === b ? 0 : a === null ? 1 : -1;
    let order: number;
    if (DECIMAL_KEYS.has(sort.key))
      order = compareDecimal(String(a), String(b));
    else if (typeof a === "number" && typeof b === "number") order = a - b;
    else
      order = String(a).localeCompare(String(b), undefined, { numeric: true });
    return order * sign;
  };
  return [...invoices].sort(
    (left, right) =>
      compare(left, right) ||
      right.issued_at.localeCompare(left.issued_at) ||
      left.invoice_number.localeCompare(right.invoice_number, undefined, {
        numeric: true,
      }),
  );
}
