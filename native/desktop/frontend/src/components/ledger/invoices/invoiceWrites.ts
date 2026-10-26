// How the invoice editor writes, and how it learns what a write whose
// outcome it did not see came to. Each write is sent once. An outcome that
// was not seen is unknown: it may have been saved, it is never sent again,
// and the editor holds further writes until the person checks the ledger,
// which reads the catalogue back and compares it with what was asked.

import {
  ledgerFailure,
  type CatalogueInvoice,
  type InvoiceAddRequest,
  type InvoiceUpdateRequest,
  type LedgerDefinitionId,
  type LedgerPort,
  type LedgerRequest,
  type LedgerResult,
} from "../../../shell/ledger";
import { readAnswer } from "../../../shell/ledgerWindow";
import { holdsCorrection, isAddedInvoice } from "./invoiceModel";

export type WriteAnswer<Result> =
  | { kind: "done"; result: Result }
  /** Settled without writing, with the runtime's code and detail. */
  | { kind: "refused"; reason: string | null; detail: unknown }
  /** Sent, and not seen to settle: it may have been saved. `saved` where
   * it did save and only its answer was not read. */
  | { kind: "unknown"; saved: boolean }
  /** Not sent, or answered nothing: nothing was written. */
  | { kind: "failed"; code: string };

export async function write<D extends LedgerDefinitionId>(
  port: LedgerPort,
  definition: D,
  payload: LedgerRequest<D>,
): Promise<WriteAnswer<LedgerResult<D>>> {
  try {
    const outcome = await port.submit(definition, payload);
    if (outcome.kind === "settled")
      return { kind: "done", result: outcome.result };
    if (outcome.kind === "refused")
      return {
        kind: "refused",
        reason: outcome.reason,
        detail: outcome.detail,
      };
    return { kind: "unknown", saved: false };
  } catch (error) {
    const failure = ledgerFailure(error);
    if (failure.code === "unknown" || failure.code === "saved_unread")
      return { kind: "unknown", saved: failure.code === "saved_unread" };
    if (failure.code === "refused")
      return { kind: "refused", reason: failure.reason ?? null, detail: null };
    return { kind: "failed", code: failure.reason ?? failure.code };
  }
}

/** What a read-back found: the write landed, it did not, or the ledger
 * could not be read, in which case the outcome stays unknown. */
export type Landed =
  | { kind: "saved"; invoice: CatalogueInvoice | null }
  | { kind: "not_saved" }
  | { kind: "unreadable" };

async function view(
  port: LedgerPort,
  invoiceId: string,
): Promise<CatalogueInvoice | null | "unreadable"> {
  try {
    const outcome = await port.submit("ledger.invoice.view", {
      invoice_id: invoiceId,
    });
    if (outcome.kind === "settled") {
      const found = outcome.result.outcome;
      return found.kind === "success" ? found.invoice : null;
    }
    if (outcome.kind === "refused") {
      const detail = outcome.detail as unknown as {
        outcome?: { reason?: string };
      } | null;
      return detail?.outcome?.reason === "not_found" ? null : "unreadable";
    }
    return "unreadable";
  } catch {
    return "unreadable";
  }
}

/** Whether an add whose outcome was not seen put its invoice in the
 * catalogue. */
export async function addLanded(
  port: LedgerPort,
  request: InvoiceAddRequest,
): Promise<Landed> {
  try {
    const answer = readAnswer(await port.submit("ledger.invoice.list", {}));
    if (answer.kind !== "answer") return { kind: "unreadable" };
    const found = answer.result.invoices.find((invoice) =>
      isAddedInvoice(invoice, request),
    );
    return found ? { kind: "saved", invoice: found } : { kind: "not_saved" };
  } catch {
    return { kind: "unreadable" };
  }
}

/** Whether a correction whose outcome was not seen is now stored. */
export async function updateLanded(
  port: LedgerPort,
  request: InvoiceUpdateRequest,
): Promise<Landed> {
  const found = await view(port, request.invoice_id);
  if (found === "unreadable" || found === null) return { kind: "unreadable" };
  return holdsCorrection(found, request)
    ? { kind: "saved", invoice: found }
    : { kind: "not_saved" };
}

/** Whether a removal whose outcome was not seen took the invoice away. */
export async function removeLanded(
  port: LedgerPort,
  invoiceId: string,
): Promise<Landed> {
  const found = await view(port, invoiceId);
  if (found === "unreadable") return { kind: "unreadable" };
  return found === null
    ? { kind: "saved", invoice: null }
    : { kind: "not_saved" };
}
