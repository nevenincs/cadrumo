// Which stored invoice a document may already be, asked of
// `ledger.invoice.duplicate`. The backend folds and compares; with no answer the
// confirmation waits.

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type {
  LedgerInvoiceDuplicateRequest,
  LedgerInvoiceDuplicateResult,
} from "./ledgerInvoiceOperations";
import type { LedgerPort } from "./ledger";
import { LatestAnswerSession, type LatestAnswer } from "./ledgerLatestAnswer";
import { readAnswer } from "./ledgerWindow";

const REST_MS = 250;

export type InvoiceDuplicateView =
  LatestAnswer<LedgerInvoiceDuplicateResult> & { retry(): void };

const sameQuestion = (
  one: LedgerInvoiceDuplicateRequest,
  other: LedgerInvoiceDuplicateRequest,
) =>
  one.kind === other.kind &&
  one.invoice_number === other.invoice_number &&
  one.counterparty_tax_id === other.counterparty_tax_id &&
  one.invoice_date === other.invoice_date &&
  one.grand_total === other.grand_total;

async function askDuplicate(
  port: LedgerPort,
  question: LedgerInvoiceDuplicateRequest,
): Promise<LatestAnswer<LedgerInvoiceDuplicateResult>> {
  const answer = readAnswer(
    await port.submit("ledger.invoice.duplicate", question),
  );
  return answer.kind === "answer"
    ? { kind: "answer", result: answer.result }
    : { kind: "failed" };
}

/** The backend's answer for what the reading now states; none until a kind is chosen. */
export function useInvoiceDuplicate(
  port: LedgerPort,
  question: LedgerInvoiceDuplicateRequest | null,
  /** A catalogue change can make or settle a duplicate, so it asks again. */
  catalogue: unknown,
): InvoiceDuplicateView {
  const [session, setSession] = useState(() => build(port));
  const answer = useSyncExternalStore(session.subscribe, session.snapshot);
  useEffect(() => {
    session.start();
    return () => session.stop();
  }, [session]);
  useEffect(() => {
    setSession((held) => {
      held.stop();
      return build(port);
    });
  }, [port, catalogue]);
  useEffect(() => {
    if (question) session.want(question);
  }, [session, question]);
  return useMemo(
    () => ({ ...answer, retry: () => session.retry() }),
    [session, answer],
  );
}

function build(port: LedgerPort) {
  return new LatestAnswerSession<
    LedgerInvoiceDuplicateRequest,
    LedgerInvoiceDuplicateResult
  >((question) => askDuplicate(port, question), sameQuestion, REST_MS);
}
