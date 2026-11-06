// What an unsaved split would come to, asked of `ledger.split.check`: the backend
// reads the amounts, works out what the last part takes and says what the split
// writer would refuse. With no answer the split waits to be added.

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type { LedgerPort } from "./ledger";
import type { LedgerSplitCheckResult } from "./ledgerMovementOperations";
import { LatestAnswerSession, type LatestAnswer } from "./ledgerLatestAnswer";
import { readAnswer } from "./ledgerWindow";

/** How long typing rests before the parts are asked about. */
const REST_MS = 150;

export type SplitCheckPart = { amount: string | null; description: string };
export type SplitCheckQuestion = {
  transactionId: string;
  parts: readonly SplitCheckPart[];
};
export type SplitCheckView = LatestAnswer<LedgerSplitCheckResult> & {
  retry(): void;
};

const sameQuestion = (one: SplitCheckQuestion, other: SplitCheckQuestion) =>
  one.transactionId === other.transactionId &&
  one.parts.length === other.parts.length &&
  one.parts.every(
    (part, at) =>
      part.amount === other.parts[at]!.amount &&
      part.description === other.parts[at]!.description,
  );

async function askSplitCheck(
  port: LedgerPort,
  { transactionId, parts }: SplitCheckQuestion,
): Promise<LatestAnswer<LedgerSplitCheckResult>> {
  const answer = readAnswer(
    await port.submit("ledger.split.check", {
      transaction_id: transactionId,
      parts: parts.map((part) => ({ ...part })),
    }),
  );
  return answer.kind === "answer"
    ? { kind: "answer", result: answer.result }
    : { kind: "failed" };
}

/** The backend's answer for these unsaved parts of a movement. */
export function useSplitCheck(
  port: LedgerPort,
  transactionId: string,
  parts: readonly SplitCheckPart[],
): SplitCheckView {
  const [session] = useState(
    () =>
      new LatestAnswerSession<SplitCheckQuestion, LedgerSplitCheckResult>(
        (question) => askSplitCheck(port, question),
        sameQuestion,
        REST_MS,
      ),
  );
  const answer = useSyncExternalStore(session.subscribe, session.snapshot);
  useEffect(() => {
    session.start();
    return () => session.stop();
  }, [session]);
  useEffect(() => {
    session.want({ transactionId, parts });
  }, [session, transactionId, parts]);
  return useMemo(
    () => ({ ...answer, retry: () => session.retry() }),
    [session, answer],
  );
}
