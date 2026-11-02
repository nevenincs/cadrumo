// What an unsaved rule pattern would find, asked of `ledger.rule.trial`: the
// patterns are the backend's regular expressions, read by its engine, so the
// window tries none itself. An answer belongs to the exact question asked. One
// question is out at a time, because the backend refuses a second while the
// first runs: the latest is asked once the running one settles, a stale reply
// says nothing, and with no answer the draft stays and the save waits.

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type { LedgerPort, LedgerRow, LedgerRuleTrialResult } from "./ledger";
import { readAnswer } from "./ledgerWindow";

/** How long typing rests before the pattern is asked about. */
const REST_MS = 250;

export type RuleTrial =
  | { kind: "waiting" }
  | { kind: "failed" }
  | { kind: "answer"; result: LedgerRuleTrialResult };

export type RuleTrialView = RuleTrial & { retry(): void };

export type RuleTrialQuestion = {
  pattern: string;
  ids: readonly string[];
};

const WAITING: RuleTrial = { kind: "waiting" };

const sameQuestion = (
  one: RuleTrialQuestion | null,
  other: RuleTrialQuestion | null,
) =>
  one !== null &&
  other !== null &&
  one.pattern === other.pattern &&
  one.ids === other.ids;

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

export class RuleTrialSession {
  private view = WAITING;
  private readonly listeners = new Set<() => void>();
  private wanted: RuleTrialQuestion | null = null;
  private settled: { question: RuleTrialQuestion; trial: RuleTrial } | null =
    null;
  private sending = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private running = true;

  constructor(
    private readonly ask: (question: RuleTrialQuestion) => Promise<RuleTrial>,
    private readonly restMs = REST_MS,
  ) {}

  readonly subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  readonly snapshot = () => this.view;

  want(question: RuleTrialQuestion): void {
    if (sameQuestion(question, this.wanted)) return;
    this.clearTimer();
    this.wanted = question.pattern === "" ? null : question;
    this.publish();
    if (this.wanted === null || this.isSettled(this.wanted)) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.send();
    }, this.restMs);
  }

  /** Asks again about a question whose answer failed. */
  retry(): void {
    if (this.settled?.trial.kind === "failed") this.settled = null;
    this.clearTimer();
    this.publish();
    this.send();
  }

  start(): void {
    this.running = true;
  }
  stop(): void {
    this.running = false;
    this.clearTimer();
    // A later start asks again rather than waiting on a timer now gone.
    this.wanted = null;
  }

  private isSettled(question: RuleTrialQuestion): boolean {
    return sameQuestion(question, this.settled?.question ?? null);
  }

  private clearTimer(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }

  private send(): void {
    const asked = this.wanted;
    if (!this.running || this.sending || !asked || this.isSettled(asked))
      return;
    this.sending = true;
    void this.ask(asked)
      .catch((): RuleTrial => ({ kind: "failed" }))
      .then((trial) => this.settle(asked, trial));
  }

  private settle(asked: RuleTrialQuestion, trial: RuleTrial): void {
    this.sending = false;
    if (!this.running) return;
    // Only the latest question's reply counts; the one that overtook it is
    // asked about now unless typing is still resting.
    if (!sameQuestion(asked, this.wanted)) {
      if (this.timer === null) this.send();
      return;
    }
    this.settled = { question: asked, trial };
    this.publish();
  }

  private publish(): void {
    this.view =
      this.wanted && this.isSettled(this.wanted)
        ? this.settled!.trial
        : WAITING;
    this.listeners.forEach((listener) => listener());
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
