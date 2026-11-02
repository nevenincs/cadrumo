import {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { LedgerOutcome } from "../../shell/ledger";
import type { ModeloPort } from "../../shell/modelo";
import type { ModeloWriteHolds } from "../../shell/modeloWriteHolds";
import { WriteHoldNotice, useModeloWriteHold } from "./WriteHoldNotice";
import { runOperation, type OperationRun } from "./dialogs/operationRun";

type Scope = {
  holds: ModeloWriteHolds;
  target: string;
  port: ModeloPort;
  onWritten?: () => void;
  reload: () => Promise<boolean>;
};
const Context = createContext<Scope | null>(null);

export function ModeloWriteScope({
  holds,
  target,
  port,
  onWritten,
  reload,
  children,
}: Scope & { children: ReactNode }) {
  const value = useMemo(
    () => ({ holds, target, port, onWritten, reload }),
    [holds, target, port, onWritten, reload],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

/** Modal writers need the same notice inside their active focus layer. */
export function ScopedWriteHoldNotice() {
  const scope = useContext(Context);
  const pending = useRef(false);
  const [refreshing, setRefreshing] = useState(false);
  if (!scope) return null;
  const reload = async () => {
    if (pending.current) return;
    pending.current = true;
    setRefreshing(true);
    try {
      await scope.reload();
    } finally {
      pending.current = false;
      setRefreshing(false);
    }
  };
  return (
    <WriteHoldNotice
      holds={scope.holds}
      target={scope.target}
      port={scope.port}
      onReload={() => void reload()}
      refreshing={refreshing}
      onCompleted={scope.onWritten}
    />
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
  const { holds, target, port, onWritten } = scope;
  const hold = useModeloWriteHold(holds, target);
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
      const lease = holds.begin(target);
      if (!lease) return null;
      onWritten?.();
      const outcome = await runOperation(port, send, current);
      if (outcome.kind === "unknown") holds.unknown(lease, outcome.operationId);
      else if (outcome.kind === "settled" || outcome.kind === "saved_unread")
        holds.needsRead(lease, outcome.kind === "saved_unread");
      else holds.notWritten(lease);
      // A list may have been read while the operation was pending. Completion
      // invalidates that old read even when the originating view is now gone.
      onWritten?.();
      return current() ? outcome : null;
    },
    [holds, target, port, onWritten],
  );
  return { ...scope, hold, run };
}
