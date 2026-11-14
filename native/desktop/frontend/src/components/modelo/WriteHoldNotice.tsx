import { useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { ledgerFailure, servedRefusalWords } from "../../shell/ledger";
import type { ModeloPort } from "../../shell/modelo";
import {
  reviewableFailedCalculation,
  type ModeloWriteHolds,
} from "../../shell/modeloWriteHolds";
import { useStrings } from "../../shell/strings";

export const useModeloWriteHold = (holds: ModeloWriteHolds, target: string) =>
  useSyncExternalStore(
    holds.subscribe,
    () => holds.get(target),
    () => undefined,
  );

/** Whether the window is reading its own settled write on `target`. */
export const useModeloReading = (holds: ModeloWriteHolds, target: string) =>
  useSyncExternalStore(
    holds.subscribe,
    () => holds.isReading(target),
    () => false,
  );

export const useModeloBlockingWriteHold = (
  holds: ModeloWriteHolds,
  target: string,
) =>
  useSyncExternalStore(
    holds.subscribe,
    () => holds.blocking(target),
    () => undefined,
  );

export const useModeloReviewedFailure = (
  holds: ModeloWriteHolds,
  target: string,
) =>
  useSyncExternalStore(
    holds.subscribe,
    () => holds.reviewedFailure(target),
    () => undefined,
  );

/** An arbitrary read cannot release an unknown operation. A person may explicitly
 * review a proven terminal calculation failure. */
export function WriteHoldNotice({
  holds,
  target,
  port,
  onReload,
  onReviewCurrent,
  refreshing = false,
  creation = false,
  onCompleted,
}: {
  holds: ModeloWriteHolds;
  target: string;
  port: ModeloPort;
  onReload?: () => void;
  onReviewCurrent?: () => Promise<boolean>;
  refreshing?: boolean;
  creation?: boolean;
  onCompleted?: () => void;
}) {
  const t = useStrings();
  const hold = useModeloWriteHold(holds, target);
  const reviewed = useModeloReviewedFailure(holds, target);
  const reading = useModeloReading(holds, target);
  const generation = useRef(0);
  useLayoutEffect(
    () => () => {
      ++generation.current;
    },
    [holds, target, port, onReviewCurrent],
  );
  const pending = useRef(new Set<string>());
  const [checking, setChecking] = useState<string | null>(null);
  if (!hold)
    return reviewed ? (
      <Alert
        tone="warning"
        role="alert"
        icon={<Icon name="alert" />}
        className="modelo-write-hold"
      >
        {reviewed.refusal_words && <p>{reviewed.refusal_words}</p>}
        <p>{t("workspace.modelo.write_hold.reviewed_calculation")}</p>
      </Alert>
    ) : null;
  if (hold.phase === "running") return null;
  // The window reads its own settled write by itself; the notice and its
  // control stay for a read the person started, served words, or a failed read.
  if (hold.phase === "refresh" && reading && !refreshing && !hold.words)
    return null;
  const canReview =
    !creation &&
    onReviewCurrent !== undefined &&
    reviewableFailedCalculation(hold);
  const terminalFailure =
    hold.phase === "unknown" ? hold.terminalFailure : undefined;
  const review = async () => {
    if (!canReview || !onReviewCurrent || pending.current.has(target)) return;
    pending.current.add(target);
    setChecking(target);
    const mine = generation.current;
    try {
      await holds.reviewCalculation(
        hold,
        onReviewCurrent,
        () => mine === generation.current,
      );
    } finally {
      pending.current.delete(target);
      if (mine === generation.current) setChecking(null);
    }
  };
  const check = async () => {
    if (
      hold.phase !== "unknown" ||
      hold.operationId === null ||
      pending.current.has(target)
    )
      return;
    pending.current.add(target);
    setChecking(target);
    try {
      const outcome = await port.observe(hold.operationId);
      if (
        outcome.operation_id === hold.operationId &&
        (outcome.kind === "settled" || outcome.kind === "refused")
      ) {
        holds.needsRead(
          hold,
          false,
          outcome.kind === "refused"
            ? servedRefusalWords(outcome.detail)
            : null,
        );
        onCompleted?.();
      }
      // A running/review operation, or a failed observation, stays unknown.
    } catch (error) {
      const failure = ledgerFailure(error);
      if (
        holds.get(target) === hold &&
        failure.terminal_failure?.operation_id === hold.operationId
      )
        holds.unknown(hold, hold.operationId, failure.terminal_failure);
      // Terminal failure words explain the stop; unresolved effects stay held.
    } finally {
      pending.current.delete(target);
      setChecking((current) => (current === target ? null : current));
    }
  };
  return (
    <Alert
      tone="warning"
      role="alert"
      icon={<Icon name="unknown" />}
      className="modelo-write-hold"
    >
      <p>
        {hold.phase === "refresh"
          ? t(
              hold.savedUnread
                ? "workspace.modelo.write_hold.saved_unread"
                : "workspace.modelo.write_hold.reload_needed",
            )
          : terminalFailure
            ? t("workspace.modelo.write_hold.terminal_failed")
            : t(
                hold.operationId === null
                  ? "workspace.modelo.write_hold.unresolved"
                  : "workspace.modelo.write_hold.unknown",
              )}
      </p>
      {hold.phase === "refresh" && hold.words && <p>{hold.words}</p>}
      {terminalFailure?.refusal_words && <p>{terminalFailure.refusal_words}</p>}
      {canReview && (
        <p>{t("workspace.modelo.write_hold.review_calculation_hint")}</p>
      )}
      {canReview && (
        <Button
          size="sm"
          variant="outline"
          disabled={checking === target}
          onClick={() => void review()}
        >
          {checking === target && <Spinner />}
          {t("workspace.modelo.write_hold.review_calculation")}
        </Button>
      )}
      {hold.phase === "refresh"
        ? onReload && (
            <Button
              size="sm"
              variant="outline"
              disabled={refreshing}
              onClick={onReload}
            >
              {refreshing && <Spinner />}
              {t(
                creation
                  ? "workspace.modelo.write_hold.reload_list"
                  : "workspace.modelo.read_again",
              )}
            </Button>
          )
        : hold.operationId !== null && (
            <Button
              size="sm"
              variant="outline"
              disabled={checking === target}
              onClick={() => void check()}
            >
              {checking === target && <Spinner />}
              {t("workspace.modelo.write_hold.check_status")}
            </Button>
          )}
    </Alert>
  );
}
