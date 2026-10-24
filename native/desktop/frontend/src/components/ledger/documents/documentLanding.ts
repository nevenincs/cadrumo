// How the Documents section learns where a write it did not see settle
// ended: each check reads the register the write touched and says saved,
// not saved, repeatable or untold. Null means the read did not answer, so
// the write stays held.

import type {
  EvidenceUpdateRequest,
  InvoiceKind,
  LedgerPort,
} from "../../../shell/ledger";
import { readAnswer } from "../../../shell/ledgerWindow";
import type { LandingCheck } from "../WritePause";
import { holdsUpdate } from "./documentsModel";

const EVIDENCE_NOT_FOUND = "REFUSED_LEDGER_EVIDENCE_NOT_FOUND";

/** When the reading of `reference` waiting for review was drafted: null
 * where none waits, undefined while the queue could not be read. */
export async function pendingDraftedAt(
  port: LedgerPort,
  reference: string,
): Promise<string | null | undefined> {
  try {
    const answer = readAnswer(
      await port.submit("ledger.evidence.review.list", {}),
    );
    if (answer.kind !== "answer") return undefined;
    return (
      (answer.result.rows ?? []).find(
        (row) => row.evidence_reference === reference,
      )?.drafted_at ?? null
    );
  } catch {
    return undefined;
  }
}

/** A read of `reference`'s document: every read that lands replaces the
 * waiting draft with a newly drafted one, so a draft drafted after
 * `before` is this read's, and none, or the one from before, is not. */
export function extractionLanding(
  port: LedgerPort,
  reference: string,
  before: string | null,
): LandingCheck {
  return async () => {
    const drafted = await pendingDraftedAt(port, reference);
    if (drafted === undefined) return null;
    return drafted !== null && drafted !== before ? "saved" : "not_saved";
  };
}

/** A confirmation of `reference`'s reading as invoice `number` of `kind`:
 * a confirmed reading leaves the queue and its invoice is in the
 * catalogue. Still waiting is not saved; gone without that invoice is
 * not told. */
export function confirmationLanding(
  port: LedgerPort,
  reference: string,
  sent: { kind: InvoiceKind; number: string | null },
): LandingCheck {
  return async () => {
    const drafted = await pendingDraftedAt(port, reference);
    if (drafted === undefined) return null;
    if (drafted !== null) return "not_saved";
    try {
      const answer = readAnswer(
        await port.submit("ledger.invoice.list", { kind: sent.kind }),
      );
      if (answer.kind !== "answer") return null;
      return sent.number !== null &&
        answer.result.invoices.some(
          (invoice) => invoice.invoice_number === sent.number,
        )
        ? "saved"
        : "untold";
    } catch {
      return null;
    }
  };
}

/** An evidence record's correction, or with `request` null its removal:
 * saved when the record holds every corrected field, or is gone. */
export function recordLanding(
  port: LedgerPort,
  evidenceId: string,
  request: EvidenceUpdateRequest | null,
): LandingCheck {
  return async () => {
    try {
      const settled = await port.submit("ledger.evidence.view", {
        evidence_id: evidenceId,
      });
      // The view settles a missing record as its declared refusal.
      const absent =
        settled.kind === "refused" && settled.reason === EVIDENCE_NOT_FOUND;
      if (absent) return request === null ? "saved" : "not_saved";
      const answer = readAnswer(settled);
      if (answer.kind !== "answer") return null;
      const outcome = answer.result.outcome;
      if (request === null)
        return outcome.kind === "refused" ? "saved" : "not_saved";
      return outcome.kind === "success" && holdsUpdate(outcome.record, request)
        ? "saved"
        : "not_saved";
    } catch {
      return null;
    }
  };
}
