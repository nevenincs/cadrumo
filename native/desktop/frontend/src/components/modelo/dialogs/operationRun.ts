import {
  ledgerFailure,
  type LedgerFailureCode,
  type LedgerOutcome,
} from "../../../shell/ledger";
import type { ModeloPort } from "../../../shell/modelo";

// One write, sent once and followed until it settles. A write that may have
// reached the runtime and whose settlement was not seen is unknown: it may
// have committed, so the caller never sends it again and holds further
// writes of its kind until the declaration is read again.

export type OperationRun<Result> =
  | { kind: "settled"; result: Result }
  /** The runtime settled it without changing anything. */
  | { kind: "refused"; operationId: string; reason: string | null }
  /** The request never reached the runtime; nothing was changed. */
  | { kind: "not_sent"; code: LedgerFailureCode }
  /** It committed, and its result could not be read. */
  | { kind: "saved_unread" }
  | { kind: "unknown"; operationId: string | null };

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
    if (failure.code === "refused" && failure.operation_id !== null)
      return {
        kind: "refused",
        operationId: failure.operation_id,
        reason: failure.reason ?? null,
      };
    if (NOT_SENT.has(failure.code))
      return { kind: "not_sent", code: failure.code };
    return { kind: "unknown", operationId: failure.operation_id };
  }
  for (;;) {
    if (outcome.kind === "settled")
      return { kind: "settled", result: outcome.result };
    if (outcome.kind === "refused")
      return {
        kind: "refused",
        operationId: outcome.operation_id,
        reason: outcome.reason,
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
    } catch {
      return { kind: "unknown", operationId: operation };
    }
  }
}
