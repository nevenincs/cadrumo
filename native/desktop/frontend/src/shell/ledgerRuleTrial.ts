// What an unsaved rule pattern would find, asked of `ledger.rule.trial`: the
// patterns are the backend's regular expressions, read by its engine, so the
// window tries none itself. An answer belongs to the exact question asked; the
// latest wins, and with no answer the draft stays and the save waits.

import { useEffect, useMemo, useState } from "react";
import type { LedgerPort, LedgerRow, LedgerRuleTrialResult } from "./ledger";
import { readAnswer } from "./ledgerWindow";

/** How long typing rests before the pattern is asked about. */
const REST_MS = 250;

export type RuleTrial =
  | { kind: "waiting" }
  | { kind: "failed" }
  | { kind: "answer"; result: LedgerRuleTrialResult };

async function askRuleTrial(
  port: LedgerPort,
  pattern: string,
  ids: readonly string[],
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

/** The backend's answer for `pattern` over the movements loaded. */
export function useRuleTrial(
  port: LedgerPort,
  pattern: string,
  rows: readonly LedgerRow[] | null | undefined,
): RuleTrial {
  const ids = useMemo(
    () => (rows ?? []).map((row) => row.transaction.transaction_id),
    [rows],
  );
  const [held, setHeld] = useState<{
    pattern: string;
    ids: readonly string[];
    trial: RuleTrial;
  } | null>(null);
  useEffect(() => {
    if (pattern === "") return;
    let current = true;
    const rest = setTimeout(() => {
      void askRuleTrial(port, pattern, ids).then((trial) => {
        if (current) setHeld({ pattern, ids, trial });
      });
    }, REST_MS);
    return () => {
      current = false;
      clearTimeout(rest);
    };
  }, [port, pattern, ids]);
  return held !== null && held.pattern === pattern && held.ids === ids
    ? held.trial
    : { kind: "waiting" };
}
