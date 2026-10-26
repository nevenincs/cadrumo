// How the Documents section says what a reading holds: a field's name,
// where its value came from in plain words, a finding's reason, a batch
// item's outcome and an attachment's source. Nothing here decides anything.

import type {
  AttachmentSource,
  ConfirmationBlockReason,
  EvidenceBatchItemStatus,
  FieldGrounding,
  FieldOrigin,
  FieldProvenance,
} from "../../../shell/ledger";
import type { Translate } from "../../../shell/strings";
import type {
  ConfirmHold,
  CorrectionField,
  ReadingField,
} from "./documentsModel";

export const FIELD_NAMES = [
  "supplier_name",
  "supplier_tax_id",
  "customer_name",
  "customer_tax_id",
  "counterparty_name",
  "counterparty_tax_id",
  "invoice_number",
  "series",
  "invoice_series",
  "invoice_date",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "recargo_amount",
  "retention_rate",
  "retencion_rate",
  "retention_amount",
  "retencion_amount",
  "grand_total",
  "currency",
] as const;

/** A field's name, from the reading or the confirmation. A field the page
 * does not know is shown as itself. */
export function fieldLabel(
  t: Translate,
  field: ReadingField | CorrectionField | string,
): string {
  return (FIELD_NAMES as readonly string[]).includes(field)
    ? t(`desktop.ledger.documents.field.${field}`)
    : field;
}

const ORIGINS: readonly FieldOrigin[] = [
  "exact_structured",
  "text_layer",
  "text_rules",
  "vision",
  "tabular_mapped",
  "operator",
  "derived",
];
const GROUNDINGS: readonly FieldGrounding[] = [
  "reconciled",
  "anchored",
  "unanchored",
  "ambiguous",
  "contradicted",
];

/** Where a value came from and whether the page agrees, in plain words:
 * "Read from the PDF, totals agree". */
export function provenanceText(t: Translate, found: FieldProvenance): string {
  const origin = ORIGINS.includes(found.origin)
    ? t(`desktop.ledger.documents.origin.${found.origin}`)
    : found.origin;
  const grounding = GROUNDINGS.includes(found.grounding)
    ? t(`desktop.ledger.documents.grounding.${found.grounding}`)
    : found.grounding;
  return t("desktop.ledger.documents.provenance", { origin, grounding });
}
/** Whether a value's grounding asks the person to look again. */
export const doubtful = (found: FieldProvenance | null) =>
  found !== null &&
  (found.grounding === "ambiguous" ||
    found.grounding === "contradicted" ||
    found.grounding === "unanchored");

const REASONS: readonly ConfirmationBlockReason[] = [
  "closure_discrepancy",
  "ambiguous_identity",
  "unresolved_direction",
  "contradicted_regime",
  "undetermined_establishment",
  "unmodelled_invoice_class",
  "contradicted_invoice_class",
];
export const reasonLabel = (t: Translate, reason: string) =>
  (REASONS as readonly string[]).includes(reason)
    ? t(`desktop.ledger.documents.reason.${reason}`)
    : reason;

const STATUSES: readonly EvidenceBatchItemStatus[] = [
  "ingested",
  "no_op",
  "refused",
  "pending_review",
  "paused",
];
export const batchStatusLabel = (t: Translate, status: string) =>
  (STATUSES as readonly string[]).includes(status)
    ? t(`desktop.ledger.documents.batch_status.${status}`)
    : status;

const SOURCES: readonly AttachmentSource[] = [
  "LOCAL_FILE",
  "GMAIL",
  "GOOGLE_DRIVE",
  "URL",
  "INLINE",
];
export const sourceLabel = (t: Translate, source: string) =>
  (SOURCES as readonly string[]).includes(source)
    ? t(`desktop.ledger.documents.source.${source.toLowerCase()}`)
    : source;

export const holdText = (t: Translate, hold: ConfirmHold) =>
  t(`desktop.ledger.documents.hold.${hold}`);
