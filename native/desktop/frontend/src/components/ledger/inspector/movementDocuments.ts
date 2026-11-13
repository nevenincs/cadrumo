import type { LedgerEvidenceRecordProjection } from "../../../shell/ledgerDocumentContract";
import type { LedgerTransaction } from "../../../shell/ledger";

/** A purchase evidence reference and supplementary blob references are
 * independent canonical facts. Linking one never implies storing the other. */
export function movementDocuments(
  transaction: Pick<
    LedgerTransaction,
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

/** Once purchase evidence is linked it is immutable. A later document is
 * supplementary, so its blob is attached without replacing that reference. */
export function documentAttachmentReference(
  transaction: Pick<LedgerTransaction, "purchase_invoice_evidence_id">,
  record: LedgerEvidenceRecordProjection,
) {
  return transaction.purchase_invoice_evidence_id
    ? { evidenceId: null, attachmentIds: [record.attachment_id] }
    : { evidenceId: record.evidence_id, attachmentIds: [] };
}
