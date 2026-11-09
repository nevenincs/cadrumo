import {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import type { LedgerOutcome } from "../../shell/ledger";
import type { ModeloPort } from "../../shell/modelo";
import {
  modeloWriteConflicts,
  type ModeloWriteHold,
  type ModeloWriteHolds,
  type ModeloWriteOwner,
} from "../../shell/modeloWriteHolds";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
  WriteHoldNotice,
  useModeloBlockingWriteHold,
  useModeloReviewedFailure,
} from "./WriteHoldNotice";
import { runOperation, type OperationRun } from "./dialogs/operationRun";

type Scope = {
  holds: ModeloWriteHolds;
  target: string;
  port: ModeloPort;
  onWritten?: () => void;
  reload: () => Promise<boolean>;
  owner?: ModeloWriteOwner;
  reloadHold?: (hold: ModeloWriteHold) => Promise<boolean>;
  onOpenOwner?: (owner: ModeloWriteOwner) => void;
};
const Context = createContext<Scope | null>(null);

export function ModeloWriteScope({
  holds,
  target,
  port,
  onWritten,
  reload,
  owner,
  reloadHold,
  onOpenOwner,
  children,
}: Scope & { children: ReactNode }) {
  const value = useMemo(
    () => ({
      holds,
      target,
      port,
      onWritten,
      reload,
      owner,
      reloadHold,
      onOpenOwner,
    }),
    [holds, target, port, onWritten, reload, owner, reloadHold, onOpenOwner],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

/** Modal writers need the same notice inside their active focus layer. */
export function ScopedWriteHoldNotice({
  exclude = [],
}: { exclude?: readonly string[] } = {}) {
  const scope = useContext(Context);
  return scope ? <ScopeNotices scope={scope} exclude={exclude} /> : null;
}

function ScopeNotices({
  scope,
  exclude,
}: {
  scope: Scope;
  exclude: readonly string[];
}) {
  const snapshot = useSyncExternalStore(
    scope.holds.subscribe,
    scope.holds.snapshot,
    scope.holds.snapshot,
  );
  const pending = useRef(false);
  const [refreshing, setRefreshing] = useState(false);
  const reload = async (hold: ModeloWriteHold) => {
    if (pending.current) return;
    pending.current = true;
    setRefreshing(true);
    try {
      if (scope.reloadHold) await scope.reloadHold(hold);
      else if (hold.key === scope.target) await scope.reload();
    } finally {
      pending.current = false;
      setRefreshing(false);
    }
  };
  const reviewed = useModeloReviewedFailure(scope.holds, scope.target);
  return (
    <>
      {reviewed && !exclude.includes(scope.target) && (
        <WriteHoldNotice
          holds={scope.holds}
          target={scope.target}
          port={scope.port}
        />
      )}
      {snapshot
        .filter(
          (hold) =>
            !exclude.includes(hold.key) &&
            modeloWriteConflicts(scope.target, hold),
        )
        .map((hold) => {
          const owner = hold.owner;
          if (hold.phase === "running" && (!owner || hold.key === scope.target))
            return null;
          const foreign =
            hold.key !== scope.target &&
            owner &&
            scope.owner?.workUnitId !== owner.workUnitId;
          return (
            <div key={hold.key} aria-busy={hold.phase === "running"}>
              {owner && hold.key !== scope.target && (
                <div className="flex items-center gap-2 text-sm">
                  {foreign && scope.onOpenOwner ? (
                    <Button
                      variant="link"
                      className="h-auto p-0"
                      onClick={() => scope.onOpenOwner?.(owner)}
                    >
                      {owner.label}
                    </Button>
                  ) : (
                    <span>{owner.label}</span>
                  )}
                  {hold.phase === "running" && <Spinner />}
                </div>
              )}
              <WriteHoldNotice
                holds={scope.holds}
                target={hold.key}
                port={scope.port}
                onReload={!foreign ? () => void reload(hold) : undefined}
                onReviewCurrent={
                  hold.key === scope.target ? scope.reload : undefined
                }
                refreshing={refreshing}
                onCompleted={scope.onWritten}
              />
            </div>
          );
        })}
    </>
  );
}

export function useModeloWriteScope() {
  const scope = useContext(Context);
  if (!scope) throw new Error("Modelo writes require their declaration scope");
  return scope;
}

/** All writers of one declaration share admission and outcome evidence,
 * including writers whose original dialog or view has since gone away. */
export function useModeloOperation() {
  const scope = useModeloWriteScope();
  const { holds, target, port, onWritten, owner } = scope;
  const hold = useModeloBlockingWriteHold(holds, target);
  const reviewedFailure = useModeloReviewedFailure(holds, target);
  const generation = useRef(0);
  useLayoutEffect(
    () => () => {
      ++generation.current;
    },
    [holds, target, port],
  );
  const run = useCallback(
    async <Result,>(
      send: () => Promise<LedgerOutcome<Result>>,
      alive: () => boolean,
    ): Promise<OperationRun<Result> | null> => {
      if (!alive()) return null;
      const mine = generation.current;
      const current = () => alive() && mine === generation.current;
      const lease = holds.begin(target, owner);
      if (!lease) return null;
      onWritten?.();
      const outcome = await runOperation(port, send, current);
      if (outcome.kind === "unknown")
        holds.unknown(lease, outcome.operationId, outcome.terminalFailure);
      else if (outcome.kind === "settled" || outcome.kind === "saved_unread")
        holds.needsRead(lease, outcome.kind === "saved_unread");
      else holds.notWritten(lease);
      // A list may have been read while the operation was pending. Completion
      // invalidates that old read even when the originating view is now gone.
      onWritten?.();
      return current() ? outcome : null;
    },
    [holds, target, port, onWritten, owner],
  );
  return { ...scope, hold, reviewedFailure, run };
}
