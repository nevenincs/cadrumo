import { useRef, useState, useSyncExternalStore } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { servedRefusalWords } from "../../shell/ledger";
import type { ModeloPort } from "../../shell/modelo";
import type { ModeloWriteHolds } from "../../shell/modeloWriteHolds";
import { useStrings } from "../../shell/strings";

export const useModeloWriteHold = (holds: ModeloWriteHolds, target: string) =>
  useSyncExternalStore(
    holds.subscribe,
    () => holds.get(target),
    () => undefined,
  );

/** A read of the form/list is not evidence that an unknown operation ended. */
export function WriteHoldNotice({
  holds,
  target,
  port,
  onReload,
  refreshing = false,
  creation = false,
}: {
  holds: ModeloWriteHolds;
  target: string;
  port: ModeloPort;
  onReload: () => void;
  refreshing?: boolean;
  creation?: boolean;
}) {
  const t = useStrings();
  const hold = useModeloWriteHold(holds, target);
  const pending = useRef(new Set<string>());
  const [checking, setChecking] = useState<string | null>(null);
  if (!hold || hold.phase === "running") return null;
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
      if (outcome.kind === "settled" || outcome.kind === "refused")
        holds.needsRead(
          hold,
          false,
          outcome.kind === "refused"
            ? servedRefusalWords(outcome.detail)
            : null,
        );
      // A running/review operation, or a failed observation, stays unknown.
    } catch {
      // No successful observation means no evidence to unlock this target.
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
          : t(
              hold.operationId === null
                ? "workspace.modelo.write_hold.unresolved"
                : "workspace.modelo.write_hold.unknown",
            )}
      </p>
      {hold.phase === "refresh" && hold.words && <p>{hold.words}</p>}
      {hold.phase === "refresh" ? (
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
      ) : (
        hold.operationId !== null && (
          <Button
            size="sm"
            variant="outline"
            disabled={checking === target}
            onClick={() => void check()}
          >
            {checking === target && <Spinner />}
            {t("workspace.modelo.write_hold.check_status")}
          </Button>
        )
      )}
    </Alert>
  );
}
