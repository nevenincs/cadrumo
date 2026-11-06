// Which movement settles which invoice, asked of `ledger.invoice.match`. The
// ledger weighs the flow, currency and amount and ranks the candidates; the
// window shows what it says. With no answer the matching waits, and a failed
// read says it failed rather than that nothing matches.

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type {
  LedgerInvoiceMatchRequest,
  LedgerInvoiceMatchResult,
  LedgerInvoiceMatchStagedLink,
} from "./ledgerInvoiceOperations";
import type { LedgerPort } from "./ledger";
import { LatestAnswerSession, type LatestAnswer } from "./ledgerLatestAnswer";
import { readAnswer } from "./ledgerWindow";

const REST_MS = 100;

export type InvoiceMatchView = LatestAnswer<LedgerInvoiceMatchResult> & {
  retry(): void;
};

const sameLinks = (
  one: readonly LedgerInvoiceMatchStagedLink[],
  other: readonly LedgerInvoiceMatchStagedLink[],
) =>
  one.length === other.length &&
  one.every(
    (link, at) =>
      link.transaction_id === other[at]!.transaction_id &&
      link.invoice_id === other[at]!.invoice_id,
  );

const sameQuestion = (
  one: LedgerInvoiceMatchRequest,
  other: LedgerInvoiceMatchRequest,
) =>
  (one.invoice_id ?? null) === (other.invoice_id ?? null) &&
  (one.transaction_id ?? null) === (other.transaction_id ?? null) &&
  sameLinks(one.staged, other.staged) &&
  sameLinks(one.judge ?? [], other.judge ?? []);

async function askMatches(
  port: LedgerPort,
  question: LedgerInvoiceMatchRequest,
): Promise<LatestAnswer<LedgerInvoiceMatchResult>> {
  const answer = readAnswer(
    await port.submit("ledger.invoice.match", question),
  );
  return answer.kind === "answer"
    ? { kind: "answer", result: answer.result }
    : { kind: "failed" };
}

function build(port: LedgerPort) {
  return new LatestAnswerSession<
    LedgerInvoiceMatchRequest,
    LedgerInvoiceMatchResult
  >((question) => askMatches(port, question), sameQuestion, REST_MS);
}

/**
 * The ledger's proposals for these staged links; none until there is a
 * question. `fresh` names what the answer depends on beyond the question,
 * such as a new read of the movements, and asks again when it changes.
 */
export function useInvoiceMatches(
  port: LedgerPort,
  question: LedgerInvoiceMatchRequest | null,
  fresh: unknown,
): InvoiceMatchView {
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
  }, [port, fresh]);
  useEffect(() => {
    if (question) session.want(question);
  }, [session, question]);
  return useMemo(
    () => ({ ...answer, retry: () => session.retry() }),
    [session, answer],
  );
}
