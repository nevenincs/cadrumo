// What the inspector's Documents section says about a stored document's
// bytes and about releasing a movement's purchase document, in the words of
// the tokens the ledger serves, and how it learns where a check or a release
// whose outcome it did not see ended.

import type { LedgerPort } from "../../../shell/ledger";
import type {
  EvidenceUnreadableCause,
  LedgerEvidenceRecordProjection,
} from "../../../shell/ledgerDocumentContract";
import type {
  LedgerPurchaseEvidenceReleaseRefusal,
  PurchaseEvidenceReleaseCause,
  PurchaseEvidenceReleaseNextStep,
} from "../../../shell/ledgerInvoiceContract";
import { readAnswer } from "../../../shell/ledgerWindow";
import type { LandingCheck } from "../WritePause";

/** Why a check found a document's stored file unreadable. */
export const UNREADABLE_CAUSE_WORDS: Record<EvidenceUnreadableCause, string> = {
  "ledger.evidence.bytes_readable":
    "desktop.ledger.inspector.documents.readability.cause.bytes_readable",
  "ledger.evidence.document_bytes_available":
    "desktop.ledger.inspector.documents.readability.cause.document_bytes_available",
};

/** Why a release of the movement's purchase document was refused. */
export const RELEASE_CAUSE_WORDS: Record<PurchaseEvidenceReleaseCause, string> =
  {
    transaction_not_found:
      "desktop.ledger.inspector.documents.release.cause.transaction_not_found",
    no_linked_purchase_evidence:
      "desktop.ledger.inspector.documents.release.cause.no_linked_purchase_evidence",
    transaction_changed:
      "desktop.ledger.inspector.documents.release.cause.transaction_changed",
    transaction_not_editable:
      "desktop.ledger.inspector.documents.release.cause.transaction_not_editable",
    finalized_calculation_reference:
      "desktop.ledger.inspector.documents.release.cause.finalized_calculation_reference",
    evidence_confirmed_into_invoice:
      "desktop.ledger.inspector.documents.release.cause.evidence_confirmed_into_invoice",
    reference_has_no_stored_document:
      "desktop.ledger.inspector.documents.release.cause.reference_has_no_stored_document",
  };

/** What the person can do about a refused release. */
export const RELEASE_STEP_WORDS: Record<
  PurchaseEvidenceReleaseNextStep,
  string
> = {
  reopen_transaction:
    "desktop.ledger.inspector.documents.release.next_step.reopen_transaction",
  restore_transaction:
    "desktop.ledger.inspector.documents.release.next_step.restore_transaction",
  reopen_finalized_calculation:
    "desktop.ledger.inspector.documents.release.next_step.reopen_finalized_calculation",
  link_movement_to_invoice:
    "desktop.ledger.inspector.documents.release.next_step.link_movement_to_invoice",
  detach_instead:
    "desktop.ledger.inspector.documents.release.next_step.detach_instead",
};

/** The typed refusal a refused release carries in its detail, or null where
 * the detail holds none. */
export function releaseRefusalOf(
  detail: unknown,
): LedgerPurchaseEvidenceReleaseRefusal | null {
  if (typeof detail !== "object" || detail === null) return null;
  const refusal = (detail as { refusal?: unknown }).refusal;
  if (typeof refusal !== "object" || refusal === null) return null;
  const { cause, next_step } = refusal as Record<string, unknown>;
  return typeof cause === "string" &&
    cause in RELEASE_CAUSE_WORDS &&
    typeof next_step === "string" &&
    next_step in RELEASE_STEP_WORDS
    ? (refusal as LedgerPurchaseEvidenceReleaseRefusal)
    : null;
}

/** A check of `record` whose outcome was not seen: saved once the record
 * carries a finding, not saved while it is still unchecked. */
export function verifyLanding(
  port: LedgerPort,
  record: LedgerEvidenceRecordProjection,
): LandingCheck {
  return async () => {
    try {
      const answer = readAnswer(
        await port.submit("ledger.evidence.view", {
          evidence_id: record.evidence_id,
        }),
      );
      if (answer.kind !== "answer") return null;
      const outcome = answer.result.outcome;
      if (outcome.kind !== "success") return "untold";
      return outcome.record.readability === "unchecked" ? "not_saved" : "saved";
    } catch {
      return null;
    }
  };
}

/** A release of `evidenceId` from movement `transactionId` whose outcome was
 * not seen: saved once the movement no longer links it, not saved while it
 * still does. */
export function releaseLanding(
  port: LedgerPort,
  transactionId: string,
  evidenceId: string,
): LandingCheck {
  return async () => {
    try {
      const answer = readAnswer(
        await port.submit("ledger.view", {
          transaction_prefix: transactionId,
        }),
      );
      if (answer.kind !== "answer") return null;
      const linked = answer.result.transaction.purchase_invoice_evidence_id;
      return linked === evidenceId
        ? "not_saved"
        : linked === null
          ? "saved"
          : "untold";
    } catch {
      return null;
    }
  };
}
