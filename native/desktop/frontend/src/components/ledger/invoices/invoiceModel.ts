// What the Invoices section works out before it asks the ledger anything:
// a line's subtotal and IVA from what the person typed, the invoice's
// totals, the retención its rate implies, the next number of a series, and
// the request an add or a correction sends. Every figure is exact decimal
// text; nothing here is rounded through a float. The ledger decides: these
// checks only say early what it would refuse.

import {
  INVOICE_UPDATE_FIELDS,
  type CatalogueInvoice,
  type InvoiceAddLine,
  type InvoiceAddRequest,
  type InvoiceKind,
  type InvoiceUpdateField,
  type InvoiceUpdateRequest,
  type InvoiceUpdateValues,
  type PaymentStatus,
  type PublicDecimal,
} from "../../../shell/ledger";
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
  periodSpan,
  type GrammarRefusal,
  type LedgerPeriod,
} from "../../../shell/ledgerGrammar";

// ---- Exact decimals --------------------------------------------------------

type Exact = { units: bigint; scale: number };
function exact(text: string): Exact | null {
  const found = /^(\d+)(?:\.(\d+))?$/.exec(text);
  if (!found) return null;
  const fraction = found[2] ?? "";
  return { units: BigInt(`${found[1]}${fraction}`), scale: fraction.length };
}
function atScale(number: Exact, scale: number): bigint {
  return number.units * 10n ** BigInt(scale - number.scale);
}
function textOf(number: Exact): string {
  const digits = number.units.toString().padStart(number.scale + 1, "0");
  const whole = digits.slice(0, digits.length - number.scale);
  const fraction = digits.slice(digits.length - number.scale);
  return canonicalDecimal(fraction ? `${whole}.${fraction}` : whole)!;
}
const ZERO: Exact = { units: 0n, scale: 0 };
function plus(left: Exact, right: Exact): Exact {
  const scale = Math.max(left.scale, right.scale);
  return { units: atScale(left, scale) + atScale(right, scale), scale };
}
function minus(left: Exact, right: Exact): Exact {
  const scale = Math.max(left.scale, right.scale);
  return { units: atScale(left, scale) - atScale(right, scale), scale };
}
function times(left: Exact, right: Exact): Exact {
  return { units: left.units * right.units, scale: left.scale + right.scale };
}
/** To the cent, half away from zero. */
function cents(number: Exact): Exact {
  if (number.scale <= 2) return { units: atScale(number, 2), scale: 2 };
  const divisor = 10n ** BigInt(number.scale - 2);
  const whole = number.units / divisor;
  const rest = number.units % divisor;
  return {
    units: rest * 2n >= divisor ? whole + 1n : whole,
    scale: 2,
  };
}
const read = (text: string) => exact(text) ?? ZERO;

/** The sum of decimal texts, in canonical spelling. */
export function sumDecimals(values: readonly string[]): string {
  return textOf(values.map(read).reduce(plus, ZERO));
}
/** `left` less `right`, in canonical spelling; null below zero. */
export function lessDecimal(left: string, right: string): string | null {
  const difference = minus(read(left), read(right));
  return difference.units < 0n ? null : textOf(difference);
}
/** `left` times `right`, to the cent. */
export function timesToCent(left: string, right: string): string {
  return textOf(cents(times(read(left), read(right))));
}
/** Whether two amounts differ by more than one cent. */
function apartByMoreThanACent(left: string, right: string): boolean {
  const difference = minus(read(left), read(right));
  const scale = Math.max(difference.scale, 2);
  const units = atScale(difference, scale);
  const magnitude = units < 0n ? -units : units;
  return magnitude > atScale({ units: 1n, scale: 2 }, scale);
}

// ---- Vocabularies -----------------------------------------------------------

/** The registry's IVA rate slots for an invoice line, in its order, with
 * the fraction each numeric slot stands for. Exempt and not-subject lines
 * carry no IVA. */
export const RATE_SLOTS = [
  { slot: "RATE_0", fraction: "0" },
  { slot: "RATE_2", fraction: "0.02" },
  { slot: "RATE_4", fraction: "0.04" },
  { slot: "RATE_5", fraction: "0.05" },
  { slot: "RATE_7.5", fraction: "0.075" },
  { slot: "RATE_10", fraction: "0.1" },
  { slot: "RATE_21", fraction: "0.21" },
  { slot: "EXEMPT", fraction: null },
  { slot: "NOT_SUBJECT", fraction: null },
] as const;
export type RateSlot = (typeof RATE_SLOTS)[number]["slot"];
export const isRateSlot = (slot: string): slot is RateSlot =>
  RATE_SLOTS.some((found) => found.slot === slot);
const slotFraction = (slot: RateSlot) =>
  RATE_SLOTS.find((found) => found.slot === slot)!.fraction;

/** The registry's invoice classes, by their tokens. */
export const INVOICE_CLASSES = [
  "ORDINARIA",
  "SIMPLIFICADA",
  "RECTIFICATIVA",
] as const;
export type InvoiceClass = (typeof INVOICE_CLASSES)[number];
export const isInvoiceClass = (value: string): value is InvoiceClass =>
  (INVOICE_CLASSES as readonly string[]).includes(value);

export const PAYMENT_STATUSES: readonly PaymentStatus[] = [
  "PENDING",
  "PARTIALLY_PAID",
  "PAID",
  "OVERDUE",
  "CANCELLED",
];

/** The Modelo 349 operation keys an invoice may carry. */
export const OPERATION_TYPES = [
  "E",
  "H",
  "M",
  "S",
  "T",
  "R",
  "A",
  "I",
  "D",
  "C",
] as const;

/** Where a leased business premises is, as the record design codes it. */
export const PREMISES_SITUATIONS = ["1", "2", "3", "4"] as const;

/** The retención rates offered with one press. */
export const RETENTION_PRESETS = ["15", "7", "19"] as const;

// ---- Lines -------------------------------------------------------------------

/** One line as typed. `rate` is a slot, or empty until one is chosen. */
export type LineDraft = {
  key: string;
  description: string;
  quantity: string;
  unitPrice: string;
  rate: string;
  category: string;
};

export const emptyLine = (key: string): LineDraft => ({
  key,
  description: "",
  quantity: "1",
  unitPrice: "",
  rate: "",
  category: "",
});

/** Why a value was not taken: the grammar's refusal, or a missing fact. */
export type Problem =
  | { kind: "grammar"; refusal: GrammarRefusal }
  | { kind: "missing" }
  | { kind: "rule"; rule: RuleProblem; values?: Record<string, string> };
export type RuleProblem =
  | "choose_kind"
  | "country_letters"
  | "currency_letters"
  | "tax_id_required"
  | "series_required"
  | "rectifies_required"
  | "choose_rate"
  | "no_line"
  | "recargo_above_iva"
  | "printed_differs"
  | "retention_above_base"
  | "retention_needs_amount"
  | "retention_differs"
  | "lease_reference_not_allowed"
  | "payment_id_shape"
  | "operation_date_fixed";

export type LineFigures = {
  /** Something was typed on it beyond the quantity it opens with. */
  entered: boolean;
  /** Every fact it needs is there and taken. */
  complete: boolean;
  subtotal: string | null;
  iva: string | null;
  problems: Partial<
    Record<"description" | "quantity" | "unitPrice" | "rate", Problem>
  >;
};

const grammar = (refusal: GrammarRefusal): Problem => ({
  kind: "grammar",
  refusal,
});

/** A line's subtotal and IVA, to the cent, from its quantity, price and
 * rate, and what keeps it from being complete. */
export function lineFigures(line: LineDraft): LineFigures {
  const problems: LineFigures["problems"] = {};
  const entered =
    line.description.trim() !== "" ||
    line.unitPrice.trim() !== "" ||
    line.rate !== "" ||
    line.category !== "" ||
    (line.quantity.trim() !== "" && line.quantity.trim() !== "1");
  const description = parseLine(line.description, 4096);
  if (description.kind === "refused")
    problems.description = grammar(description.refusal);
  else if (description.kind === "empty")
    problems.description = { kind: "missing" };
  const quantity = parseDecimal(line.quantity, QUANTITY_RULE);
  if (quantity.kind === "refused")
    problems.quantity = grammar(quantity.refusal);
  else if (quantity.kind === "empty") problems.quantity = { kind: "missing" };
  const price = parseDecimal(line.unitPrice, UNIT_PRICE_RULE);
  if (price.kind === "refused") problems.unitPrice = grammar(price.refusal);
  else if (price.kind === "empty") problems.unitPrice = { kind: "missing" };
  if (!isRateSlot(line.rate))
    problems.rate = { kind: "rule", rule: "choose_rate" };
  const subtotal =
    quantity.kind === "value" && price.kind === "value"
      ? timesToCent(quantity.value, price.value)
      : null;
  let iva: string | null = null;
  if (subtotal !== null && isRateSlot(line.rate)) {
    const fraction = slotFraction(line.rate);
    iva = fraction === null ? "0" : timesToCent(subtotal, fraction);
  }
  return {
    entered,
    complete: Object.keys(problems).length === 0,
    subtotal,
    iva,
    problems,
  };
}

// ---- Totals and retención ----------------------------------------------------

export type Totals = {
  base: string;
  iva: string;
  recargo: string | null;
  total: string;
};

/** What the lines add up to, with the recargo inside the total. */
export function invoiceTotals(
  figures: readonly LineFigures[],
  recargo: string | null,
): Totals {
  const counted = figures.filter((line) => line.complete);
  const base = sumDecimals(counted.map((line) => line.subtotal!));
  const iva = sumDecimals(counted.map((line) => line.iva!));
  return {
    base,
    iva,
    recargo,
    total: sumDecimals([base, iva, recargo ?? "0"]),
  };
}

/** The retención a rate implies on `base`, to the cent. */
export const retentionFor = (base: string, rateFraction: string) =>
  timesToCent(base, rateFraction);

/** What the retención fields come to: the rate, the amount, and what is
 * wrong with them against the base. Retención stays outside the total. */
export type RetentionFigures = {
  rate: string | null;
  amount: string | null;
  /** The amount the rate implies, where a rate is given. */
  implied: string | null;
  problems: Partial<Record<"rate" | "amount", Problem>>;
};

/** The retención rate a draft holds, read as points: the draft takes `15`,
 * `0.5` or `0.5%` as percentages, so a bare number is never taken for a
 * fraction. The value is the fraction the wire carries. */
function retentionRate(text: string): ReturnType<typeof parsePercent> {
  const typed = text.trim();
  return parsePercent(typed === "" || typed.endsWith("%") ? text : `${typed}%`);
}

export function retentionFigures(
  base: string,
  rateText: string,
  amountText: string,
): RetentionFigures {
  const problems: RetentionFigures["problems"] = {};
  const rate = retentionRate(rateText);
  const amount = parseDecimal(amountText, TAX_AMOUNT_RULE);
  if (rate.kind === "refused") problems.rate = grammar(rate.refusal);
  if (amount.kind === "refused") problems.amount = grammar(amount.refusal);
  const rateValue = rate.kind === "value" ? rate.value : null;
  const amountValue = amount.kind === "value" ? amount.value : null;
  const implied = rateValue === null ? null : retentionFor(base, rateValue);
  if (rateValue !== null && amount.kind === "empty")
    problems.amount = { kind: "rule", rule: "retention_needs_amount" };
  else if (amountValue !== null && compareDecimal(amountValue, base) > 0)
    problems.amount = { kind: "rule", rule: "retention_above_base" };
  else if (
    amountValue !== null &&
    implied !== null &&
    apartByMoreThanACent(amountValue, implied)
  )
    problems.amount = {
      kind: "rule",
      rule: "retention_differs",
      values: { amount: implied },
    };
  return { rate: rateValue, amount: amountValue, implied, problems };
}

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
  /** The amount was typed, not worked out from the rate. */
  retentionTouched: boolean;
  lease: boolean;
  situacion: string;
  referencia: string;
  notes: string;
  lines: LineDraft[];
};

export const emptyDraft = (firstLine: string): InvoiceDraft => ({
  kind: null,
  invoiceClass: "ORDINARIA",
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
  retentionTouched: false,
  lease: false,
  situacion: "",
  referencia: "",
  notes: "",
  lines: [emptyLine(firstLine)],
});

/** The retención amount the draft shows: typed, or worked out from its
 * rate until the person types one. */
export function shownRetentionAmount(
  draft: Pick<
    InvoiceDraft,
    "retentionRate" | "retentionAmount" | "retentionTouched"
  >,
  base: string,
): string {
  if (draft.retentionTouched) return draft.retentionAmount;
  const rate = retentionRate(draft.retentionRate);
  return rate.kind === "value" ? retentionFor(base, rate.value) : "";
}

/** The four facts every new invoice needs, named before anything is sent. */
export const CREATION_INVARIANTS = [
  "counterparty",
  "country",
  "line",
  "totals",
] as const;
export type CreationInvariant = (typeof CREATION_INVARIANTS)[number];

export type DraftCheck = {
  lines: LineFigures[];
  totals: Totals;
  retention: RetentionFigures;
  /** Which of the four invariants hold now. */
  invariants: Record<CreationInvariant, boolean>;
  /** Field problems, by field; a line's by `line:<key>:<field>`. */
  problems: Record<string, Problem>;
  /** The request, where nothing above is wrong. */
  request: InvoiceAddRequest | null;
};

const COUNTRY = /^[A-Za-z]{2}$/;
const CURRENCY = /^[A-Za-z]{3}$/;
const decimal = (value: string): PublicDecimal => ({ decimal: value });
/** A one-line text field: its value, or its problem. */
function textField(
  raw: string,
  max: number,
): { value: string | null; problem: Problem | null } {
  const parsed = parseLine(raw, max);
  if (parsed.kind === "refused")
    return { value: null, problem: grammar(parsed.refusal) };
  return {
    value: parsed.kind === "value" ? parsed.value : null,
    problem: null,
  };
}

/** Everything the editor knows about a new invoice, and the request it
 * would send. */
export function checkDraft(draft: InvoiceDraft): DraftCheck {
  const problems: Record<string, Problem> = {};
  const lines = draft.lines.map(lineFigures);
  // A line nobody typed on is left out; a line begun must be finished.
  const counted = lines.filter((line) => line.entered);
  draft.lines.forEach((line, at) => {
    const figures = lines[at]!;
    if (!figures.entered) return;
    for (const [field, problem] of Object.entries(figures.problems))
      problems[`line:${line.key}:${field}`] = problem;
  });
  const recargoParsed = parseDecimal(draft.recargo, TAX_AMOUNT_RULE);
  const recargo = recargoParsed.kind === "value" ? recargoParsed.value : null;
  if (recargoParsed.kind === "refused")
    problems.recargo = grammar(recargoParsed.refusal);
  const totals = invoiceTotals(lines, recargo);
  if (recargo !== null && compareDecimal(recargo, totals.iva) > 0)
    problems.recargo = { kind: "rule", rule: "recargo_above_iva" };
  const printed = parseDecimal(draft.printedTotal, TAX_AMOUNT_RULE);
  if (printed.kind === "refused") problems.printed = grammar(printed.refusal);
  else if (
    printed.kind === "value" &&
    compareDecimal(printed.value, totals.total) !== 0
  )
    problems.printed = {
      kind: "rule",
      rule: "printed_differs",
      values: { total: totals.total },
    };
  const retention = retentionFigures(
    totals.base,
    draft.retentionRate,
    shownRetentionAmount(draft, totals.base),
  );
  if (retention.problems.rate)
    problems.retention_rate = retention.problems.rate;
  if (retention.problems.amount)
    problems.retention_amount = retention.problems.amount;

  if (draft.kind === null)
    problems.kind = { kind: "rule", rule: "choose_kind" };
  const name = textField(draft.counterpartyName, 512);
  if (name.problem) problems.counterparty_name = name.problem;
  else if (name.value === null)
    problems.counterparty_name = { kind: "missing" };
  const country = draft.country.trim();
  if (!COUNTRY.test(country))
    problems.counterparty_country =
      country === ""
        ? { kind: "missing" }
        : { kind: "rule", rule: "country_letters" };
  const currency = draft.currency.trim();
  if (!CURRENCY.test(currency))
    problems.currency =
      currency === ""
        ? { kind: "missing" }
        : { kind: "rule", rule: "currency_letters" };
  const number = textField(draft.number, 128);
  if (number.problem) problems.invoice_number = number.problem;
  else if (number.value === null) problems.invoice_number = { kind: "missing" };
  const issued = parseIsoDate(draft.issuedAt);
  if (issued.kind === "refused") problems.issued_at = grammar(issued.refusal);
  else if (issued.kind === "empty") problems.issued_at = { kind: "missing" };
  const operation = parseIsoDate(draft.operationDate);
  if (operation.kind === "refused")
    problems.operation_date = grammar(operation.refusal);
  const taxId = textField(draft.taxId, 64);
  if (taxId.problem) problems.counterparty_tax_id = taxId.problem;
  else if (
    taxId.value === null &&
    !(draft.kind === "issued" && draft.invoiceClass === "SIMPLIFICADA")
  )
    problems.counterparty_tax_id = { kind: "rule", rule: "tax_id_required" };
  const series = textField(draft.series, 64);
  if (series.problem) problems.series = series.problem;
  const rectifies = textField(draft.rectifies, 128);
  if (rectifies.problem) problems.rectifies_invoice_number = rectifies.problem;
  if (draft.invoiceClass === "RECTIFICATIVA") {
    if (series.value === null && !series.problem)
      problems.series = { kind: "rule", rule: "series_required" };
    if (rectifies.value === null && !rectifies.problem)
      problems.rectifies_invoice_number = {
        kind: "rule",
        rule: "rectifies_required",
      };
  }
  const leased = draft.kind === "issued" && draft.lease;
  const referencia = textField(draft.referencia, 25);
  if (leased && referencia.problem) problems.referencia = referencia.problem;
  else if (
    leased &&
    referencia.value !== null &&
    (draft.situacion === "3" || draft.situacion === "4")
  )
    problems.referencia = { kind: "rule", rule: "lease_reference_not_allowed" };

  const complete = counted.filter((line) => line.complete);
  if (complete.length === 0 && counted.length === 0)
    problems.lines = { kind: "rule", rule: "no_line" };

  const invariants: Record<CreationInvariant, boolean> = {
    counterparty: !problems.counterparty_name,
    country: !problems.counterparty_country,
    line: complete.length > 0 && complete.length === counted.length,
    totals:
      complete.length > 0 &&
      complete.length === counted.length &&
      !problems.recargo &&
      !problems.printed,
  };

  let request: InvoiceAddRequest | null = null;
  if (Object.keys(problems).length === 0 && draft.kind !== null) {
    const received = draft.kind === "received";
    request = {
      kind: draft.kind,
      counterparty_name: name.value!,
      counterparty_tax_id: taxId.value,
      counterparty_country: country.toUpperCase(),
      invoice_number: number.value!,
      issued_at: issued.kind === "value" ? issued.value : "",
      currency: currency.toUpperCase(),
      notes: draft.notes.trim(),
      invoice_class: draft.invoiceClass,
      lines: draft.lines.flatMap((line, at): InvoiceAddLine[] => {
        const figures = lines[at]!;
        if (!figures.entered) return [];
        return [
          {
            description: line.description.trim(),
            quantity: decimal(canonicalDecimal(line.quantity.trim())!),
            unit_price: decimal(canonicalDecimal(line.unitPrice.trim())!),
            subtotal: decimal(figures.subtotal!),
            iva_rate: line.rate,
            iva_amount: decimal(figures.iva!),
            ...(received && line.category
              ? { spending_category_id: line.category }
              : {}),
          },
        ];
      }),
      ...(series.value !== null ? { series: series.value } : {}),
      ...(operation.kind === "value"
        ? { operation_date: operation.value }
        : {}),
      ...(draft.ivaCategory ? { iva_category: draft.ivaCategory } : {}),
      ...(draft.operationType ? { operation_type: draft.operationType } : {}),
      ...(draft.invoiceClass === "RECTIFICATIVA" && rectifies.value !== null
        ? { rectifies_invoice_number: rectifies.value }
        : {}),
      ...(recargo !== null ? { recargo_amount: decimal(recargo) } : {}),
      ...(retention.rate !== null
        ? { retention_rate: decimal(retention.rate) }
        : {}),
      ...(retention.amount !== null
        ? { retention_amount: decimal(retention.amount) }
        : {}),
      ...(leased
        ? {
            business_premises_lease: {
              situacion_inmueble: draft.situacion || null,
              referencia_catastral: referencia.value,
            },
          }
        : {}),
    };
  }
  return { lines, totals, retention, invariants, problems, request };
}

/** Whether a stored invoice is the one `request` asked to add: the same
 * identity, read back after an add whose outcome was not seen. */
export function isAddedInvoice(
  invoice: CatalogueInvoice,
  request: InvoiceAddRequest,
): boolean {
  const total = invoiceTotalsOfRequest(request);
  return (
    invoice.kind === request.kind &&
    invoice.invoice_number === request.invoice_number &&
    invoice.issued_at === request.issued_at &&
    invoice.currency === request.currency &&
    (invoice.counterparty_tax_id ?? "").toUpperCase().replace(/[\s-]/g, "") ===
      (request.counterparty_tax_id ?? "").toUpperCase().replace(/[\s-]/g, "") &&
    compareDecimal(invoice.grand_total.decimal, total) === 0
  );
}
function invoiceTotalsOfRequest(request: InvoiceAddRequest): string {
  const lines = request.lines ?? [];
  return sumDecimals([
    ...lines.map((line) => line.subtotal.decimal),
    ...lines.map((line) => line.iva_amount.decimal),
    request.recargo_amount?.decimal ?? "0",
  ]);
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
    series: string;
    year: number;
  },
): NumberSuggestion | null {
  if (want.kind !== "issued") return null;
  const typed = want.series.trim();
  if (!typed && want.invoiceClass === "RECTIFICATIVA") return null;
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
  retentionTouched: boolean;
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
    retentionRate: rate === null ? "" : (percentText(rate) ?? ""),
    retentionAmount: invoice.retention_amount
      ? (canonicalDecimal(invoice.retention_amount.decimal) ?? "")
      : "",
    retentionTouched: true,
    series: invoice.series ?? "",
    invoiceClass: invoice.invoice_class,
    rectifies: invoice.rectifies_invoice_number ?? "",
    paymentId: "",
  };
}
function percentText(fraction: string): string | null {
  const number = exact(fraction);
  if (!number) return null;
  return textOf({ units: number.units * 100n, scale: number.scale });
}

export type CorrectionCheck = {
  /** The fields whose value differs from the stored one. */
  changed: InvoiceUpdateField[];
  problems: Record<string, Problem>;
  retention: RetentionFigures;
  request: InvoiceUpdateRequest | null;
};

const HEX64 = /^[0-9a-f]{64}$/;

/** Whether `text` has the shape of a payment id: a transaction id, 64 lowercase
 * hex digits. */
export const isPaymentId = (text: string) => HEX64.test(text);

/** The correction a draft makes to `invoice`, field by field, and what the
 * ledger would refuse in it. Only the fields the update accepts are ever
 * sent, and only those that changed. */
export function checkCorrection(
  invoice: CatalogueInvoice,
  draft: CorrectionDraft,
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
  const name = textField(draft.counterpartyName, 512);
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
    // A stored operation date has its role beside it, which no correction
    // can set: a date can be moved, not added or taken away.
    if (next !== invoice.operation_date) {
      if (next === null || invoice.operation_date === null)
        problems.operation_date = {
          kind: "rule",
          rule: "operation_date_fixed",
        };
      else set("operation_date", next);
    }
  }
  const series = textField(draft.series, 64);
  if (series.problem) problems.series = series.problem;
  else if (series.value !== invoice.series) set("series", series.value);
  if (draft.invoiceClass !== invoice.invoice_class)
    set("invoice_class", draft.invoiceClass);
  const rectifies = textField(draft.rectifies, 128);
  const rectificativa = draft.invoiceClass === "RECTIFICATIVA";
  const rectified = rectificativa ? rectifies.value : null;
  // Only a rectificativa names the invoice it rectifies: leaving that class
  // takes the number away.
  if (rectificativa && rectifies.problem)
    problems.rectifies_invoice_number = rectifies.problem;
  else if (rectified !== invoice.rectifies_invoice_number)
    set("rectifies_invoice_number", rectified);
  if (rectificativa) {
    if (series.value === null && !series.problem)
      problems.series = { kind: "rule", rule: "series_required" };
    if (rectifies.value === null && !rectifies.problem)
      problems.rectifies_invoice_number = {
        kind: "rule",
        rule: "rectifies_required",
      };
  }
  const base = invoice.base_total.decimal;
  const retention = retentionFigures(
    base,
    draft.retentionRate,
    shownRetentionAmount(draft, base),
  );
  if (retention.problems.rate)
    problems.retention_rate = retention.problems.rate;
  if (retention.problems.amount)
    problems.retention_amount = retention.problems.amount;
  const storedRate = invoice.retention_rate?.decimal ?? null;
  const storedAmount = invoice.retention_amount?.decimal ?? null;
  const sameNumber = (left: string | null, right: string | null) =>
    left === right ||
    (left !== null && right !== null && compareDecimal(left, right) === 0);
  if (!retention.problems.rate && !sameNumber(retention.rate, storedRate))
    set(
      "retention_rate",
      retention.rate === null ? null : decimal(retention.rate),
    );
  if (!retention.problems.amount && !sameNumber(retention.amount, storedAmount))
    set(
      "retention_amount",
      retention.amount === null ? null : decimal(retention.amount),
    );
  const paymentId = draft.paymentId.trim().toLowerCase();
  if (paymentId !== "") {
    if (!isPaymentId(paymentId))
      problems.payment_id = { kind: "rule", rule: "payment_id_shape" };
    else set("payment_id", paymentId);
  }
  const ordered = INVOICE_UPDATE_FIELDS.filter((field) =>
    changed.includes(field),
  );
  return {
    changed: ordered,
    problems,
    retention,
    request:
      ordered.length > 0 && Object.keys(problems).length === 0
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
  const span = filter.period ? periodSpan(filter.period) : null;
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
