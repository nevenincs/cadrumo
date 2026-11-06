// What an unsaved rule pattern would find, asked of `ledger.rule.trial`: the
// patterns are the backend's regular expressions, read by its engine, so the
// window tries none itself. An answer belongs to the exact question asked. One
// question is out at a time, because the backend refuses a second while the
// first runs: the latest is asked once the running one settles, a stale reply
// says nothing, and with no answer the draft stays and the save waits.

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type { LedgerPort, LedgerRow } from "./ledger";
import type { LedgerRuleTrialResult } from "./ledgerMovementOperations";
import { LatestAnswerSession, type LatestAnswer } from "./ledgerLatestAnswer";
import { readAnswer } from "./ledgerWindow";

/** How long typing rests before the pattern is asked about. */
const REST_MS = 250;

export type RuleTrial = LatestAnswer<LedgerRuleTrialResult>;

export type RuleTrialView = RuleTrial & { retry(): void };

export type RuleTrialQuestion = {
  pattern: string;
  ids: readonly string[];
};

const sameQuestion = (one: RuleTrialQuestion, other: RuleTrialQuestion) =>
  one.pattern === other.pattern && one.ids === other.ids;

async function askRuleTrial(
  port: LedgerPort,
  { pattern, ids }: RuleTrialQuestion,
): Promise<RuleTrial> {
  try {
    const answer = readAnswer(
      await port.submit("ledger.rule.trial", {
        description_pattern: pattern,
        transaction_ids: [...ids],
      }),
    );
    return answer.kind === "answer"
      ? { kind: "answer", result: answer.result }
      : { kind: "failed" };
  } catch {
    return { kind: "failed" };
  }
}

export class RuleTrialSession extends LatestAnswerSession<
  RuleTrialQuestion,
  LedgerRuleTrialResult
> {
  constructor(
    ask: (question: RuleTrialQuestion) => Promise<RuleTrial>,
    restMs = REST_MS,
  ) {
    super(ask, sameQuestion, restMs, (question) => question.pattern === "");
  }
}

/** The backend's answer for `pattern` over the movements loaded. */
export function useRuleTrial(
  port: LedgerPort,
  pattern: string,
  rows: readonly LedgerRow[] | null | undefined,
): RuleTrialView {
  const ids = useMemo(
    () => (rows ?? []).map((row) => row.transaction.transaction_id),
    [rows],
  );
  const [session] = useState(
    () => new RuleTrialSession((question) => askRuleTrial(port, question)),
  );
  const trial = useSyncExternalStore(session.subscribe, session.snapshot);
  useEffect(() => {
    session.start();
    return () => session.stop();
  }, [session]);
  useEffect(() => {
    session.want({ pattern, ids });
  }, [session, pattern, ids]);
  return useMemo(
    () => ({ ...trial, retry: () => session.retry() }),
    [session, trial],
  );
}
