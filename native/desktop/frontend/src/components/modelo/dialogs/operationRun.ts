import {
  ledgerFailure,
  servedNextStep,
  servedRefusalWords,
  type LedgerErrorDetail,
  type LedgerFailureCode,
  type LedgerNextStep,
  type LedgerOutcome,
  type TerminalOperationFailure,
} from "../../../shell/ledger";
import type { ModeloPort } from "../../../shell/modelo";
import type { ModeloEditApplyBaselineV1 } from "../../../shell/modeloContract/modeloEditWork";

/** Whether a check that found `stale` stale may renew it: only the latest
 * check, on the baseline the review now holds; an overtaken check leaves the
 * renewal to the check that overtook it. */
export function mayRenew(check: {
  ticket: number;
  latest: number;
  stale: ModeloEditApplyBaselineV1;
  current: ModeloEditApplyBaselineV1 | null;
}): boolean {
  return (
    check.ticket === check.latest &&
    check.current !== null &&
    check.stale.baseline_id === check.current.baseline_id
  );
}

// One write, sent once and followed until it settles. A write that may have
// reached the runtime and whose settlement was not seen is unknown: it may
// have committed, so the caller never sends it again and holds further
// writes until its completion is observed and a later declaration read succeeds.

export type OperationRun<Result> =
  | { kind: "settled"; result: Result }
  /** The runtime settled it without changing anything. `words` is the
   * sentence the backend served for why, shown as served; null when it
   * served none. `step` is the operation the backend names for putting the
   * refusal right, null when it names none. `detail` is the registered error
   * detail the refusal settled with, for a caller that reads a context fact
   * the backend served with it; null when the refusal carried none. */
  | {
      kind: "refused";
      operationId: string;
      reason: string | null;
      words: string | null;
      step: LedgerNextStep | null;
      detail: LedgerErrorDetail | null;
    }
  /** The request never reached the runtime; nothing was changed. */
  | { kind: "not_sent"; code: LedgerFailureCode }
  /** It committed, and its result could not be read. */
  | { kind: "saved_unread" }
  | {
      kind: "unknown";
      operationId: string | null;
      terminalFailure?: TerminalOperationFailure;
    };

/** How long to wait between looks at a running write. */
const OBSERVE_MS = 400;

/** Rejections that mean the request never reached the runtime. */
const NOT_SENT: ReadonlySet<LedgerFailureCode> = new Set([
  "unavailable",
  "not_signed_in",
  "refused",
  "too_large",
  "not_admitted",
  "invalid",
  "file_unavailable",
]);

/** Sends one write through `start` and follows it with `observe` until it
 * settles, while `alive` holds; stopping early leaves it unknown. */
export async function runOperation<Result>(
  port: ModeloPort,
  start: () => Promise<LedgerOutcome<Result>>,
  alive: () => boolean,
): Promise<OperationRun<Result>> {
  let outcome: LedgerOutcome<Result>;
  try {
    outcome = await start();
  } catch (error) {
    const failure = ledgerFailure(error);
    if (failure.code === "saved_unread") return { kind: "saved_unread" };
    if (failure.code === "refused" && failure.operation_id !== null) {
      // Submit rejects with closed metadata. Read the already-settled
      // operation for its served explanation; never submit the write again.
      let detail: LedgerErrorDetail | null = null;
      try {
        const observed = await port.observe(failure.operation_id);
        if (
          observed.kind === "refused" &&
          observed.operation_id === failure.operation_id
        )
          detail = observed.detail;
      } catch {
        // The refusal is known even when its explanation cannot be read.
      }
      return {
        kind: "refused",
        operationId: failure.operation_id,
        reason: failure.reason ?? null,
        words: servedRefusalWords(detail),
        step: servedNextStep(detail),
        detail,
      };
    }
    if (NOT_SENT.has(failure.code))
      return { kind: "not_sent", code: failure.code };
    return {
      kind: "unknown",
      operationId: failure.operation_id,
      ...(failure.terminal_failure
        ? { terminalFailure: failure.terminal_failure }
        : {}),
    };
  }
  for (;;) {
    if (outcome.kind === "settled")
      return { kind: "settled", result: outcome.result };
    if (outcome.kind === "refused")
      return {
        kind: "refused",
        operationId: outcome.operation_id,
        reason: outcome.reason,
        words: servedRefusalWords(outcome.detail),
        step: servedNextStep(outcome.detail),
        detail: outcome.detail,
      };
    // A write of this family never pauses for a review; one that does is
    // not followed here, and what it did is not known.
    if (outcome.kind === "review" || !alive())
      return { kind: "unknown", operationId: outcome.operation_id };
    const operation = outcome.operation_id;
    await new Promise((done) => setTimeout(done, OBSERVE_MS));
    try {
      // The operation was this definition's; its settlement carries its
      // result under the same contract.
      outcome = (await port.observe(operation)) as LedgerOutcome<Result>;
    } catch (error) {
      const failure = ledgerFailure(error);
      return {
        kind: "unknown",
        operationId: operation,
        ...(failure.terminal_failure?.operation_id === operation
          ? { terminalFailure: failure.terminal_failure }
          : {}),
      };
    }
  }
}
