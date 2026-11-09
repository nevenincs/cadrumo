import { createContext, useCallback, useEffect, useState } from "react";
import type { AgentSession } from "./agentSession";
import { failureCode } from "../errors";
import type {
  AgentLocalEngine,
  AgentLocalEngineToken,
  AgentLocalModels,
  AgentLocalPlacement,
} from "../ipc/contract";
import type { CatalogLane, LaneModel } from "./localModelLanes";
import type { AskedModel } from "./provisioning";

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
  /** The local engine, where the host offers it. It shares the lists'
   * revision, so a change to either is read again from the other. */
  engine?: LocalEngineHost;
  /** Calls `listener` once a change made through this host stored. */
  subscribe?: (listener: (change: "list" | "engine") => void) => () => void;
};

export type LocalEngineHost = {
  read: () => Promise<AgentLocalEngine>;
  choose: (
    engine: AgentLocalEngineToken,
    placement: AgentLocalPlacement,
    expectedRevision: string,
  ) => Promise<AgentLocalEngine>;
};

/**
 * The host over `session`, or null where it offers no lists. A change made
 * through it tells its subscribers and `onChange`, so the readers of the
 * lists and of the engine read the record again.
 */
export function localModelHostOf(
  session: AgentSession | undefined,
  onChange?: (change: "list" | "engine") => void,
): LocalModelHost | null {
  if (
    !session?.localModels ||
    !session.addLocalModel ||
    !session.removeLocalModel ||
    !session.resetLocalModels
  )
    return null;
  const listeners = new Set<(change: "list" | "engine") => void>();
  const told = <T>(change: "list" | "engine", made: Promise<T>) =>
    made.then((value) => {
      onChange?.(change);
      for (const listener of [...listeners]) listener(change);
      return value;
    });
  const add = session.addLocalModel.bind(session);
  const remove = session.removeLocalModel.bind(session);
  const reset = session.resetLocalModels.bind(session);
  const readEngine = session.localEngine?.bind(session);
  const choose = session.chooseLocalEngine?.bind(session);
  return {
    read: session.localModels.bind(session),
    add: (lane, model, revision) => told("list", add(lane, model, revision)),
    remove: (lane, model, revision) =>
      told("list", remove(lane, model, revision)),
    reset: (revision) => told("list", reset(revision)),
    ...(readEngine && choose
      ? {
          engine: {
            read: readEngine,
            choose: (engine, placement, revision) =>
              told("engine", choose(engine, placement, revision)),
          },
        }
      : {}),
    subscribe: (listener) => {
      listeners.add(listener);
      return () => void listeners.delete(listener);
    },
  };
}

/** Where a model row that is showing the local AI's plan says so, to the
 * element that would otherwise show the same plan on the program's row.
 * Absent where no program row shares the screen with the model rows. */
export const ReviewClaimContext = createContext<
  ((held: boolean) => void) | null
>(null);

export type ListSnapshot =
  | { kind: "loading" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; value: AgentLocalModels };

export type ListOutcome = { kind: "saved" } | { kind: "refused"; code: string };

export type LocalModelLists = {
  snapshot: ListSnapshot;
  retry: () => void;
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
  const { read, subscribe } = host;
  // The engine shares the lists' revision: once it changed, the lists are
  // read again.
  useEffect(
    () =>
      subscribe?.((change) => {
        if (change === "engine") setReads((count) => count + 1);
      }),
    [subscribe],
  );
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

  const retry = useCallback(() => {
    setSnapshot({ kind: "loading" });
    setReads((count) => count + 1);
  }, []);
  return { snapshot, retry, busy, outcomes, change };
}

export type EngineSnapshot =
  | { kind: "none" }
  | { kind: "loading" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; value: AgentLocalEngine };

export type LocalEngineState = {
  snapshot: EngineSnapshot;
  /** The engine and placement as read, null until a readable record. */
  value: AgentLocalEngine | null;
  /** True while a change is being stored. */
  busy: boolean;
  /** The last change's refusal code, if it was refused. */
  refusal: string | null;
  change: (
    engine: AgentLocalEngineToken,
    placement: AgentLocalPlacement,
  ) => Promise<boolean>;
};

/** The local engine and placement of `host`, read again after any change to
 * the lists or the engine made through the host: they share one revision. */
export function useLocalEngine(host: LocalModelHost | null): LocalEngineState {
  const source = host?.engine ?? null;
  const subscribe = host?.subscribe;
  const [snapshot, setSnapshot] = useState<EngineSnapshot>({ kind: "none" });
  const [reads, setReads] = useState(0);
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  useEffect(
    () => subscribe?.(() => setReads((count) => count + 1)),
    [subscribe],
  );
  useEffect(() => {
    if (!source) {
      setSnapshot({ kind: "none" });
      return;
    }
    let current = true;
    source.read().then(
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
  }, [source, reads]);
  const change = useCallback(
    async (
      engine: AgentLocalEngineToken,
      placement: AgentLocalPlacement,
    ): Promise<boolean> => {
      if (!source || snapshot.kind !== "ready" || busy) return false;
      setBusy(true);
      setRefusal(null);
      try {
        const value = await source.choose(
          engine,
          placement,
          snapshot.value.revision,
        );
        setSnapshot({ kind: "ready", value });
        return true;
      } catch (error: unknown) {
        const code = failureCode(error);
        setRefusal(code);
        // Another change came first: what is stored now is read again.
        if (code === "agent_local_models_revision_conflict")
          setReads((count) => count + 1);
        return false;
      } finally {
        setBusy(false);
      }
    },
    [source, snapshot, busy],
  );
  return {
    snapshot,
    value: snapshot.kind === "ready" ? snapshot.value : null,
    busy,
    refusal,
    change,
  };
}

/**
 * Whether the local AI's plan awaiting an answer is for `lane`: the model
 * asked for belongs to it, or, with nothing asked in this window as after a
 * reload, the plan holds a part for one of its `models`.
 */
export function planIsFor({
  lane,
  models,
  reviewed,
  planned,
}: {
  lane: CatalogLane | null;
  models: readonly LaneModel[];
  /** The model asked for, while the plan holds a part for it. */
  reviewed: AskedModel | null;
  /** Whether the plan holds a part for a model. */
  planned: (model: string) => boolean;
}): boolean {
  if (!lane) return false;
  return reviewed !== null
    ? reviewed.lane === lane.id
    : models.some(({ id }) => planned(id));
}
