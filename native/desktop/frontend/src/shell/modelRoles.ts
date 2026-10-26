import { useCallback, useEffect, useState } from "react";
import { failureCode } from "../errors";
import type { AgentModelRoles } from "../ipc/contract";
import type { AgentModelLicence, AgentTransport } from "./agentSession";

// The person's model for each role that reads their documents, read from the
// agent service and changed there at the revision read. Every view that shows
// or changes a selection reads it through here, so a change made in one is
// the stored state the next one reads.

/** What a view can do with the person's selections, as the host offers it. */
export type ModelRoleHost = {
  read: () => Promise<AgentModelRoles>;
  set: (
    role: string,
    lane: string,
    model: string,
    expectedRevision: string,
  ) => Promise<AgentModelRoles>;
  clear: (role: string, expectedRevision: string) => Promise<AgentModelRoles>;
  licence?: (
    provider: string,
    transport: AgentTransport,
    model: string,
  ) => Promise<AgentModelLicence>;
};

export type RoleSnapshot =
  | { kind: "loading" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; value: AgentModelRoles };

export type RoleOutcome = { kind: "saved" } | { kind: "refused"; code: string };

/** One change to one role, made at the revision it is handed. */
export type RoleChange = {
  role: string;
  act: (revision: string) => Promise<AgentModelRoles>;
};

export type ModelRoleSelections = {
  snapshot: RoleSnapshot;
  /** The key of the change being made, if one is. */
  busy: string | null;
  /** The last outcome per key: a role, or the key a batch was made under. */
  outcomes: Record<string, RoleOutcome>;
  /** Makes `changes` in order, each at the revision the one before answered
   * with, under `key`. Stops at the first refusal, which is recorded under
   * `key`; resolves true once every change is stored. */
  change: (key: string, changes: readonly RoleChange[]) => Promise<boolean>;
  /** The host's own changes, for `change` to make. */
  set: ModelRoleHost["set"];
  clear: ModelRoleHost["clear"];
};

export function useModelRoles(host: ModelRoleHost): ModelRoleSelections {
  const [snapshot, setSnapshot] = useState<RoleSnapshot>({ kind: "loading" });
  const [reads, setReads] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, RoleOutcome>>({});
  const { read, set, clear } = host;
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
  }, [read, reads]);

  const change = useCallback(
    async (key: string, changes: readonly RoleChange[]): Promise<boolean> => {
      if (snapshot.kind !== "ready" || snapshot.value.state !== "readable")
        return false;
      let { revision } = snapshot.value;
      setBusy(key);
      try {
        for (const { act } of changes) {
          const value = await act(revision);
          setSnapshot({ kind: "ready", value });
          // A record that stopped being readable takes no further change.
          if (value.state !== "readable") return false;
          revision = value.revision;
        }
        setOutcomes((held) => ({ ...held, [key]: { kind: "saved" } }));
        return true;
      } catch (error: unknown) {
        const code = failureCode(error);
        setOutcomes((held) => ({ ...held, [key]: { kind: "refused", code } }));
        // Another change came first: what is stored now is read again.
        if (code === "agent_model_role_revision_conflict")
          setReads((count) => count + 1);
        return false;
      } finally {
        setBusy(null);
      }
    },
    [snapshot],
  );

  return { snapshot, busy, outcomes, change, set, clear };
}
