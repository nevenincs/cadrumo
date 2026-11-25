// What the window says about a refused removal of a movement's invoice
// link, in the words of the cause and next step the ledger serves with it,
// and the staged removal the inspector offers.

import type {
  InvoiceUnlinkCause,
  InvoiceUnlinkNextStep,
  LedgerUnlinkRefusal,
} from "../../../shell/ledgerMovementContract";
import type { CatalogueInvoiceSnapshot } from "../../../shell/ledgerInvoiceContract";
import type { LedgerTransactionProjection } from "../../../shell/ledgerInvoiceContract";
import type { StageEvent, StagedAction } from "../../../shell/ledgerStage";
import { facts } from "@/shell/compose";
import type { Translate } from "../../../shell/strings";
import { declarationName } from "../inspector/inspectorWords";

/** Why a removal of a movement's invoice link was refused. */
export const UNLINK_CAUSE_WORDS: Record<InvoiceUnlinkCause, string> = {
  link_not_found:
    "desktop.ledger.inspector.invoice.unlink_cause.link_not_found",
  transaction_changed:
    "desktop.ledger.inspector.invoice.unlink_cause.transaction_changed",
  invoice_changed:
    "desktop.ledger.inspector.invoice.unlink_cause.invoice_changed",
  finalized_calculation_reference:
    "desktop.ledger.inspector.invoice.unlink_cause.finalized_calculation_reference",
};

/** What the person can do about a refused removal. */
export const UNLINK_STEP_WORDS: Record<InvoiceUnlinkNextStep, string> = {
  reopen_transaction:
    "desktop.ledger.inspector.invoice.unlink_next_step.reopen_transaction",
  reopen_invoice:
    "desktop.ledger.inspector.invoice.unlink_next_step.reopen_invoice",
  reopen_finalized_calculation:
    "desktop.ledger.inspector.invoice.unlink_next_step.reopen_finalized_calculation",
};

/** The typed refusal a refused removal carries in its detail, or null where
 * the detail holds none. */
export function unlinkRefusalOf(detail: unknown): LedgerUnlinkRefusal | null {
  if (typeof detail !== "object" || detail === null) return null;
  const refusal = (detail as { refusal?: unknown }).refusal;
  if (typeof refusal !== "object" || refusal === null) return null;
  const { cause, next_step, finalized_revisions } = refusal as Record<
    string,
    unknown
  >;
  return typeof cause === "string" &&
    Object.hasOwn(UNLINK_CAUSE_WORDS, cause) &&
    typeof next_step === "string" &&
    Object.hasOwn(UNLINK_STEP_WORDS, next_step) &&
    Array.isArray(finalized_revisions)
    ? (refusal as LedgerUnlinkRefusal)
    : null;
}

/** A refused removal in words: its cause, the declarations that hold the
 * link where a finished one does, and what to do. */
export function unlinkRefusalText(
  t: Translate,
  refusal: LedgerUnlinkRefusal,
): string {
  const declarations = refusal.finalized_revisions.map((revision) =>
    declarationName(t, revision.modelo, revision.filing_year, revision.period),
  );
  return [
    t(UNLINK_CAUSE_WORDS[refusal.cause]),
    declarations.length ? facts(t, declarations) : "",
    t(UNLINK_STEP_WORDS[refusal.next_step]),
  ]
    .filter(Boolean)
    .join(" ");
}

/** The staged removal of `transaction`'s link to `invoice`, bound to the
 * movement's modification time and the invoice's linked movements as the
 * person sees them: one per movement, as a movement has one invoice. */
export function unlinkAction(
  transaction: Pick<
    LedgerTransactionProjection,
    "transaction_id" | "modified_at"
  >,
  invoice: Pick<
    CatalogueInvoiceSnapshot,
    "invoice_id" | "linked_transaction_ids"
  >,
): StagedAction {
  return {
    id: `unlink:${transaction.transaction_id}`,
    kind: "unlink",
    transactionId: transaction.transaction_id,
    invoiceId: invoice.invoice_id,
    expectedModifiedAt: transaction.modified_at,
    expectedLinkedTransactionIds: [...invoice.linked_transaction_ids],
  };
}
export const stageUnlink = (
  transaction: Pick<
    LedgerTransactionProjection,
    "transaction_id" | "modified_at"
  >,
  invoice: Pick<
    CatalogueInvoiceSnapshot,
    "invoice_id" | "linked_transaction_ids"
  >,
): StageEvent => ({
  type: "stage_action",
  action: unlinkAction(transaction, invoice),
});
