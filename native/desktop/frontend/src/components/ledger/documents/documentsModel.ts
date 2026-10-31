// The Documents section's rules: which fields of a reading are shown and
// which the person may correct, how a correction, a finding's answer and the
// confirmation are put together for the ledger, whether the catalogue
// already holds the invoice, and whether a fresh reading is still the one
// the person reviewed. A reading is a proposal: nothing here decides a tax
// value, and nothing is assumed where the reading or the person says
// nothing. Nothing here reads or writes the ledger.

import type { FieldSpec } from "../../../shared/fieldKind";
import { heldDecimal } from "../../../shared/numbers";
import type {
  CatalogueInvoice,
  ConfirmationBlocker,
  EvidenceConfirmRequest,
  EvidenceDraft,
  EvidenceRecord,
  EvidenceUpdateField,
  EvidenceUpdateRequest,
  FieldProvenance,
  FindingResolution,
  FindingResolutionAction,
  InvoiceKind,
  JsonValue,
} from "../../../shell/ledger";
import {
  TAX_AMOUNT_RULE,
  canonicalDecimal,
  parseDecimal,
  parseIsoDate,
  parseLine,
  sameDecimal,
  type Parsed,
} from "../../../shell/ledgerGrammar";
import { parsePoints } from "../setup/setupModel";

/** The longest label the confirmation and evidence contracts take. */
export const LABEL_MAX = 1024;
/** The longest note they take. */
export const NOTE_MAX = 16_384;

/** What a field holds, which decides how a typed value is read. */
export type FieldShape = "text" | "date" | "amount" | "percent" | "currency";

/** How wide a field of `shape` is drawn, as a spacing utility: a figure
 * or a rate needs a few digits, a date its ten characters; a name takes
 * the row and other text the theme's field width. Never wider than where
 * it sits. */
export function fieldWidth(shape: FieldShape | "note", name = false): string {
  const width =
    shape === "amount" || shape === "percent"
      ? "w-32"
      : shape === "date"
        ? "w-40"
        : shape === "currency"
          ? "w-24"
          : name || shape === "note"
            ? "w-full"
            : "w-field";
  return `${width} max-w-full`;
}

const SPECS: Record<FieldShape | "note", FieldSpec> = {
  text: { kind: "text", maxLength: LABEL_MAX },
  date: { kind: "date" },
  amount: { kind: "money" },
  percent: { kind: "percent", unit: "points" },
  currency: { kind: "currency" },
  note: { kind: "notes", maxLength: NOTE_MAX },
};

/** Which editor a field of `shape` is typed in. The tax id is text by shape
 * and has an editor of its own. */
export function entrySpec(
  shape: FieldShape | "note",
  field?: string,
): FieldSpec {
  return field === "counterparty_tax_id" ? { kind: "taxId" } : SPECS[shape];
}

/** A stored value as an editor holds it: a figure or a rate is seeded through
 * `heldDecimal`. */
export function seeded(shape: FieldShape | "note", text: string): string {
  return shape === "amount" || shape === "percent" ? heldDecimal(text) : text;
}

/** A field the reading table shows. `party` fields belong to the
 * supplier or the customer, and which is the counterparty depends on the
 * invoice's kind. */
export type ReadingField =
  | "supplier_name"
  | "supplier_tax_id"
  | "customer_name"
  | "customer_tax_id"
  | "invoice_number"
  | "invoice_series"
  | "invoice_date"
  | "taxable_base"
  | "iva_rate"
  | "iva_amount"
  | "recargo_amount"
  | "retencion_rate"
  | "retencion_amount"
  | "grand_total"
  | "currency";

/** What the person may correct before confirming, by the confirmation's own
 * field names. */
export type CorrectionField =
  | "counterparty_name"
  | "counterparty_tax_id"
  | "invoice_number"
  | "series"
  | "invoice_date"
  | "taxable_base"
  | "iva_rate"
  | "iva_amount"
  | "recargo_amount"
  | "retention_rate"
  | "retention_amount"
  | "currency";

export const CORRECTION_SHAPES: Record<CorrectionField, FieldShape> = {
  counterparty_name: "text",
  counterparty_tax_id: "text",
  invoice_number: "text",
  series: "text",
  invoice_date: "date",
  taxable_base: "amount",
  iva_rate: "percent",
  iva_amount: "amount",
  recargo_amount: "amount",
  retention_rate: "percent",
  retention_amount: "amount",
  currency: "currency",
};

/** The reading's field a correction stands in for, given the kind: the
 * supplier is the counterparty of an invoice received, the customer of one
 * issued. */
export function readingFieldOf(
  field: CorrectionField,
  kind: InvoiceKind,
): ReadingField {
  switch (field) {
    case "counterparty_name":
      return kind === "received" ? "supplier_name" : "customer_name";
    case "counterparty_tax_id":
      return kind === "received" ? "supplier_tax_id" : "customer_tax_id";
    case "series":
      return "invoice_series";
    case "retention_rate":
      return "retencion_rate";
    case "retention_amount":
      return "retencion_amount";
    default:
      return field;
  }
}

/** The rows of the reading table, in order. Before the kind is chosen the
 * supplier and the customer are shown as read; after, the counterparty is
 * a correctable row of its own. */
export type ReadingRow =
  | { kind: "read"; field: ReadingField }
  | { kind: "correctable"; field: CorrectionField };
export function readingRows(kind: InvoiceKind | null): ReadingRow[] {
  const parties: ReadingRow[] = kind
    ? [
        { kind: "correctable", field: "counterparty_name" },
        { kind: "correctable", field: "counterparty_tax_id" },
      ]
    : [
        { kind: "read", field: "supplier_name" },
        { kind: "read", field: "supplier_tax_id" },
        { kind: "read", field: "customer_name" },
        { kind: "read", field: "customer_tax_id" },
      ];
  return [
    ...parties,
    { kind: "correctable", field: "invoice_number" },
    { kind: "correctable", field: "series" },
    { kind: "correctable", field: "invoice_date" },
    { kind: "correctable", field: "taxable_base" },
    { kind: "correctable", field: "iva_rate" },
    { kind: "correctable", field: "iva_amount" },
    { kind: "correctable", field: "recargo_amount" },
    { kind: "correctable", field: "retention_rate" },
    { kind: "correctable", field: "retention_amount" },
    { kind: "read", field: "grand_total" },
    { kind: "correctable", field: "currency" },
  ];
}

/** A reading's value of `field` as text, or null where it read nothing.
 * Rates are whole percentages. */
export function readValue(
  draft: EvidenceDraft,
  field: ReadingField,
): string | null {
  const found = (draft as Record<string, JsonValue | undefined>)[field];
  if (found === null || found === undefined) return null;
  if (typeof found === "object" && !Array.isArray(found) && "decimal" in found)
    return typeof found.decimal === "string" ? found.decimal : null;
  return typeof found === "string" ? found : null;
}

/** Where the reading says `field` came from. */
export function provenanceOf(
  draft: EvidenceDraft,
  field: ReadingField,
): FieldProvenance | null {
  return draft.provenance?.find((found) => found.field === field) ?? null;
}

/** A correction as typed: its canonical value, a clear of a value read, or
 * a refusal. */
export type ReadCorrection = Parsed<string>;
/** Reads one typed correction into the confirmation's own spelling: dates
 * as ISO days, amounts in their shortest form, rates as whole
 * percentages, currencies as three capital letters. */
export function readCorrection(
  field: CorrectionField,
  raw: string,
): ReadCorrection {
  switch (CORRECTION_SHAPES[field]) {
    case "text":
      return parseLine(raw, LABEL_MAX);
    case "date":
      return parseIsoDate(raw);
    case "amount": {
      const parsed = parseDecimal(raw, TAX_AMOUNT_RULE);
      return parsed.kind === "value"
        ? { kind: "value", value: canonicalDecimal(parsed.value)! }
        : parsed;
    }
    case "percent":
      return parsePoints(raw);
    case "currency": {
      const text = raw.trim().toUpperCase();
      if (text === "") return { kind: "empty" };
      return /^[A-Z]{3}$/.test(text)
        ? { kind: "value", value: text }
        : {
            kind: "refused",
            refusal: { key: "not_a_number", raw },
          };
    }
  }
}

/** Whether a corrected value is the value read: no correction at all. */
export function sameAsRead(
  field: CorrectionField,
  value: string,
  read: string | null,
): boolean {
  if (read === null) return false;
  const shape = CORRECTION_SHAPES[field];
  if (shape === "amount" || shape === "percent")
    return sameDecimal(value, read);
  return value === read.trim();
}

/** The person's typed corrections, by field. */
export type Corrections = Partial<Record<CorrectionField, string>>;

/** The corrections that change the reading, in the confirmation's
 * spelling; a refused one makes the whole set refused. */
export function correctionValues(
  draft: EvidenceDraft,
  kind: InvoiceKind | null,
  corrections: Corrections,
):
  | { kind: "ok"; values: Partial<Record<CorrectionField, string>> }
  | { kind: "refused"; fields: CorrectionField[] } {
  const values: Partial<Record<CorrectionField, string>> = {};
  const refused: CorrectionField[] = [];
  for (const [field, raw] of Object.entries(corrections) as [
    CorrectionField,
    string,
  ][]) {
    if (
      kind === null &&
      (field === "counterparty_name" || field === "counterparty_tax_id")
    )
      continue;
    const parsed = readCorrection(field, raw);
    if (parsed.kind === "refused") refused.push(field);
    if (parsed.kind !== "value") continue;
    const read = readValue(draft, readingFieldOf(field, kind ?? "received"));
    if (!sameAsRead(field, parsed.value, read)) values[field] = parsed.value;
  }
  return refused.length
    ? { kind: "refused", fields: refused }
    : { kind: "ok", values };
}

// ---- Findings -------------------------------------------------------------------

/** How the person answers one finding, as far as typed. */
/** The reading fields the catalogue works out rather than keeps as read:
 * an invoice's total is its base plus its IVA, any recargo and any suplido,
 * whatever the document prints. */
export const DERIVED_FIELDS: ReadonlySet<ReadingField> = new Set<ReadingField>([
  "grand_total",
]);

export type FindingAnswer = {
  action: FindingResolutionAction;
  value: string;
  note: string;
};

/** The resolution an answer sends, or null while it is incomplete: a
 * chosen reading must be one of the finding's candidates, a supplied value
 * must say something, and an attestation must say why. */
export function resolutionOf(
  blocker: ConfirmationBlocker,
  answer: FindingAnswer | undefined,
): FindingResolution | null {
  if (!answer) return null;
  const note = answer.note.trim();
  if (answer.action === "attest")
    return note
      ? { blocker_id: blocker.blocker_id, action: "attest", value: null, note }
      : null;
  const value = answer.value.trim();
  if (!value || value.length > LABEL_MAX) return null;
  if (
    answer.action === "choose_candidate" &&
    !(blocker.candidates ?? []).some((candidate) => candidate.value === value)
  )
    return null;
  return { blocker_id: blocker.blocker_id, action: answer.action, value, note };
}

/** The findings still open, and the resolutions of those answered. An
 * answer to a finding the reading no longer raises is dropped. */
export function findingsState(
  blockers: readonly ConfirmationBlocker[],
  answers: Readonly<Record<string, FindingAnswer>>,
): { open: ConfirmationBlocker[]; resolutions: FindingResolution[] } {
  const open: ConfirmationBlocker[] = [];
  const resolutions: FindingResolution[] = [];
  for (const blocker of blockers) {
    const resolution = resolutionOf(blocker, answers[blocker.blocker_id]);
    if (resolution) resolutions.push(resolution);
    else open.push(blocker);
  }
  return { open, resolutions };
}

// ---- Confirmation ---------------------------------------------------------------

/** A reading's binding: the source bytes and the reading the ledger will
 * check before it writes. */
export type ReadingBinding = {
  sourceSha256: string;
  draftReviewSha256: string;
};

/** The evidence a reading was made from: a record, or an attachment that
 * has none. */
export type DocumentReference =
  { kind: "evidence"; id: string } | { kind: "attachment"; id: string };

/** The reference a review queue row names: the evidence record it is the
 * id of, otherwise the attachment it is the digest of. */
export function referenceOf(
  evidenceReference: string,
  records: readonly EvidenceRecord[],
): DocumentReference {
  return records.some((record) => record.evidence_id === evidenceReference)
    ? { kind: "evidence", id: evidenceReference }
    : { kind: "attachment", id: evidenceReference };
}

export const referenceFields = (reference: DocumentReference) =>
  reference.kind === "evidence"
    ? { evidence_id: reference.id }
    : { attachment_id: reference.id };

const COUNTRY = /^[A-Z]{2}$/;
export const countryAdmitted = (country: string) =>
  COUNTRY.test(country.trim().toUpperCase());

/** What still stops a confirmation, first first. */
export type ConfirmHold =
  | "choose_kind"
  | "country"
  | "currency"
  | "findings"
  | "corrections"
  | "duplicate";

/**
 * The confirmation for one reading, or what holds it. The kind and the
 * country are always the person's: neither has a default. The currency is
 * the reading's unless it read none. Only corrections that change the
 * reading are sent, and every finding must be answered.
 */
export function confirmation(input: {
  reference: DocumentReference;
  binding: ReadingBinding;
  draft: EvidenceDraft;
  blockers: readonly ConfirmationBlocker[];
  answers: Readonly<Record<string, FindingAnswer>>;
  kind: InvoiceKind | null;
  country: string;
  corrections: Corrections;
  duplicate: CatalogueInvoice | null;
  confirmAnyway: boolean;
}):
  | { kind: "ready"; request: EvidenceConfirmRequest }
  | { kind: "held"; holds: ConfirmHold[] } {
  const holds: ConfirmHold[] = [];
  if (input.kind === null) holds.push("choose_kind");
  const country = input.country.trim().toUpperCase();
  if (!COUNTRY.test(country)) holds.push("country");
  const corrected = correctionValues(
    input.draft,
    input.kind,
    input.corrections,
  );
  if (corrected.kind === "refused") holds.push("corrections");
  const values = corrected.kind === "ok" ? corrected.values : {};
  if (!values.currency && !readValue(input.draft, "currency"))
    holds.push("currency");
  const findings = findingsState(input.blockers, input.answers);
  if (findings.open.length) holds.push("findings");
  if (input.duplicate && !input.confirmAnyway) holds.push("duplicate");
  if (holds.length || input.kind === null) return { kind: "held", holds };
  return {
    kind: "ready",
    request: {
      ...referenceFields(input.reference),
      expected_source_sha256: input.binding.sourceSha256,
      expected_draft_review_sha256: input.binding.draftReviewSha256,
      kind: input.kind,
      counterparty_country: country,
      ...values,
      ...(findings.resolutions.length
        ? { resolutions: findings.resolutions }
        : {}),
    },
  };
}

const folded = (text: string | null | undefined) =>
  (text ?? "").toUpperCase().replace(/[^A-Z0-9]+/g, "");

/**
 * The catalogue invoice this reading may already be: the same kind and
 * number with no disagreeing tax id, or the same tax id, date and total.
 */
export function duplicateOf(
  draft: EvidenceDraft,
  kind: InvoiceKind | null,
  corrections: Corrections,
  invoices: readonly CatalogueInvoice[] | null,
): CatalogueInvoice | null {
  if (!invoices || kind === null) return null;
  const corrected = correctionValues(draft, kind, corrections);
  const values = corrected.kind === "ok" ? corrected.values : {};
  const number = folded(
    values.invoice_number ?? readValue(draft, "invoice_number"),
  );
  const taxId = folded(
    values.counterparty_tax_id ??
      readValue(draft, readingFieldOf("counterparty_tax_id", kind)),
  );
  const date = values.invoice_date ?? readValue(draft, "invoice_date");
  const total = readValue(draft, "grand_total");
  const same = invoices.filter((invoice) => invoice.kind === kind);
  // The same number first; only where none has it, the same party, day
  // and total.
  return (
    same.find((invoice) => {
      const theirs = folded(invoice.counterparty_tax_id);
      return (
        !!number &&
        folded(invoice.invoice_number) === number &&
        (!taxId || !theirs || taxId === theirs)
      );
    }) ??
    same.find(
      (invoice) =>
        !!taxId &&
        taxId === folded(invoice.counterparty_tax_id) &&
        date === invoice.issued_at &&
        total !== null &&
        sameDecimal(total, invoice.grand_total.decimal),
    ) ??
    null
  );
}

/** Whether two readings say the same: a fresh reading equal to the one
 * shown is the reading the person reviewed. */
export function sameReading(
  left: EvidenceDraft,
  right: EvidenceDraft,
): boolean {
  return stable(left) === stable(right);
}
function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (value && typeof value === "object")
    return `{${Object.keys(value)
      .filter((key) => (value as Record<string, unknown>)[key] !== undefined)
      .sort()
      .map(
        (key) =>
          `${JSON.stringify(key)}:${stable((value as Record<string, unknown>)[key])}`,
      )
      .join(",")}}`;
  return JSON.stringify(value ?? null);
}

// ---- Evidence records -------------------------------------------------------------

export const EVIDENCE_SHAPES: Record<EvidenceUpdateField, FieldShape | "note"> =
  {
    supplier: "text",
    invoice_number: "text",
    invoice_date: "date",
    taxable_base: "amount",
    iva_rate: "percent",
    iva_amount: "amount",
    notes: "note",
  };

/** A record's stored value of `field`, as text. Rates are percentages. */
export const recordValue = (
  record: EvidenceRecord,
  field: EvidenceUpdateField,
) => (field === "notes" ? (record.notes ?? "") : (record[field] ?? null));

/** Reads one typed record field: a blank clears it, notes excepted, which
 * are blank rather than absent. */
function readRecordField(
  field: EvidenceUpdateField,
  raw: string,
): Parsed<string | null> {
  const shape = EVIDENCE_SHAPES[field];
  if (shape === "note")
    return raw.length > NOTE_MAX
      ? { kind: "refused", refusal: { key: "too_long", raw, limit: NOTE_MAX } }
      : { kind: "value", value: raw };
  const parsed =
    shape === "text"
      ? parseLine(raw, LABEL_MAX)
      : shape === "date"
        ? parseIsoDate(raw)
        : shape === "percent"
          ? parsePoints(raw)
          : (() => {
              const amount = parseDecimal(raw, TAX_AMOUNT_RULE);
              return amount.kind === "value"
                ? ({
                    kind: "value",
                    value: canonicalDecimal(amount.value)!,
                  } as const)
                : amount;
            })();
  return parsed.kind === "empty" ? { kind: "value", value: null } : parsed;
}

/** The correction of a record, from the fields the person changed, or the
 * fields refused. Nothing changed is nothing to send. */
export function recordUpdate(
  record: EvidenceRecord,
  typed: Partial<Record<EvidenceUpdateField, string>>,
):
  | { kind: "update"; request: EvidenceUpdateRequest }
  | { kind: "unchanged" }
  | { kind: "refused"; fields: EvidenceUpdateField[] } {
  const patch: EvidenceUpdateRequest["patch"] = {};
  const fields: EvidenceUpdateField[] = [];
  const refused: EvidenceUpdateField[] = [];
  for (const [field, raw] of Object.entries(typed) as [
    EvidenceUpdateField,
    string,
  ][]) {
    const parsed = readRecordField(field, raw);
    if (parsed.kind === "refused") {
      refused.push(field);
      continue;
    }
    if (parsed.kind !== "value") continue;
    const stored = recordValue(record, field);
    const shape = EVIDENCE_SHAPES[field];
    const same =
      parsed.value === null
        ? stored === null
        : stored !== null &&
          (shape === "amount" || shape === "percent"
            ? sameDecimal(parsed.value, stored)
            : parsed.value === stored);
    if (same) continue;
    patch[field] = parsed.value;
    fields.push(field);
  }
  if (refused.length) return { kind: "refused", fields: refused };
  if (!fields.length) return { kind: "unchanged" };
  return {
    kind: "update",
    request: { evidence_id: record.evidence_id, patch, patch_fields: fields },
  };
}

/** Whether a stored record now holds the correction asked for: what a
 * check reads back after an outcome that was not seen. */
export function holdsUpdate(
  record: EvidenceRecord,
  request: EvidenceUpdateRequest,
): boolean {
  return request.patch_fields.every((field) => {
    const wanted = request.patch[field] ?? null;
    const stored = recordValue(record, field);
    if (wanted === null) return stored === null;
    if (stored === null) return false;
    const shape = EVIDENCE_SHAPES[field];
    return shape === "amount" || shape === "percent"
      ? sameDecimal(wanted, stored)
      : wanted === stored;
  });
}

/** The name a file is shown by: the last part of what the result names. */
export const fileName = (path: string) => path.split(/[\\/]/).pop() || path;
