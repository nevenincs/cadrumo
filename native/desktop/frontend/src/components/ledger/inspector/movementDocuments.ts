import type { LedgerEvidenceRecordProjection } from "../../../shell/ledgerDocumentContract";
import type { LedgerTransactionProjection } from "../../../shell/ledgerInvoiceContract";

/** A purchase evidence reference and supplementary blob references are
 * independent canonical facts. Linking one never implies storing the other. */
export function movementDocuments(
  transaction: Pick<
    LedgerTransactionProjection,
    "purchase_invoice_evidence_id" | "attachment_ids"
  >,
  records: readonly LedgerEvidenceRecordProjection[],
) {
  const purchase = transaction.purchase_invoice_evidence_id
    ? {
        evidenceId: transaction.purchase_invoice_evidence_id,
        record:
          records.find(
            (record) =>
              record.evidence_id === transaction.purchase_invoice_evidence_id,
          ) ?? null,
      }
    : null;
  return {
    purchase,
    supplementary: transaction.attachment_ids.filter(
      (attachment) => attachment !== purchase?.record?.attachment_id,
    ),
  };
}

/** What a document is on its movement, as the person said: the purchase
 * invoice, or another document. */
export type DocumentRole = "purchase" | "other";

/** The attach reference for a document in the role the person chose. Once
 * purchase evidence is linked it is immutable, so a later document can only
 * be another document: its blob is attached without replacing that
 * reference. */
export function documentAttachmentReference(
  record: LedgerEvidenceRecordProjection,
  role: DocumentRole,
) {
  return role === "purchase"
    ? { evidenceId: record.evidence_id, attachmentIds: [] }
    : { evidenceId: null, attachmentIds: [record.attachment_id] };
}
