import { useCallback, useEffect, useState } from "react";
import { failureCode } from "../errors";
import type { AgentLocalModels } from "../ipc/contract";

// The models the person added by name to the local lanes' model lists, read
// from the agent service and changed there at the revision read. The agent's
// model picker offers a local lane's models from its list; nothing here
// chooses one.

/** What a view can do with the person's lists, as the host offers it. */
export type LocalModelHost = {
  read: () => Promise<AgentLocalModels>;
  add: (
    lane: string,
    model: string,
    expectedRevision: string,
  ) => Promise<AgentLocalModels>;
  remove: (
    lane: string,
    model: string,
    expectedRevision: string,
  ) => Promise<AgentLocalModels>;
  reset: (expectedRevision: string) => Promise<AgentLocalModels>;
};

export type ListSnapshot =
  | { kind: "loading" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; value: AgentLocalModels };

export type ListOutcome = { kind: "saved" } | { kind: "refused"; code: string };

export type LocalModelLists = {
  snapshot: ListSnapshot;
  /** The key of the change being made, if one is. */
  busy: string | null;
  /** The last outcome per key. */
  outcomes: Record<string, ListOutcome>;
  /** Makes one change at the revision read, under `key`; resolves true once
   * it is stored. A refusal is recorded under `key`. */
  change: (
    key: string,
    act: (revision: string) => Promise<AgentLocalModels>,
  ) => Promise<boolean>;
};

export function useLocalModels(
  host: LocalModelHost,
  refreshVersion = 0,
): LocalModelLists {
  const [snapshot, setSnapshot] = useState<ListSnapshot>({ kind: "loading" });
  const [reads, setReads] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, ListOutcome>>({});
  const { read } = host;
  useEffect(() => {
    let current = true;
    read().then(
      (value) => {
        if (current) setSnapshot({ kind: "ready", value });
      },
      (error: unknown) => {
        if (current) setSnapshot({ kind: "failed", code: failureCode(error) });
      },
    );
    return () => {
      current = false;
    };
  }, [read, reads, refreshVersion]);

  const change = useCallback(
    async (
      key: string,
      act: (revision: string) => Promise<AgentLocalModels>,
    ): Promise<boolean> => {
      if (snapshot.kind !== "ready") return false;
      setBusy(key);
      try {
        const value = await act(snapshot.value.revision);
        setSnapshot({ kind: "ready", value });
        setOutcomes((held) => ({ ...held, [key]: { kind: "saved" } }));
        return true;
      } catch (error: unknown) {
        const code = failureCode(error);
        setOutcomes((held) => ({ ...held, [key]: { kind: "refused", code } }));
        // Another change came first: what is stored now is read again.
        if (code === "agent_local_models_revision_conflict")
          setReads((count) => count + 1);
        return false;
      } finally {
        setBusy(null);
      }
    },
    [snapshot],
  );

  return { snapshot, busy, outcomes, change };
}
