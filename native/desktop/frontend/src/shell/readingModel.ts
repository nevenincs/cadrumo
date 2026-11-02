import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { failureCode } from "../errors";
import type { AgentListedModel, AgentLocalModels } from "../ipc/contract";

// The model documents are read with is the one the person selected in the
// agent's model picker. The picker keeps that choice in the window; the agent
// service keeps it beside the local model lists, where a tax worker's reading
// finds it. This keeps the service's copy the picker's, and reads the lists
// the picker offers local models from.

/** Reading and storing the model documents are read with, as the host offers it. */
export type ReadingModelHost = {
  read: () => Promise<AgentLocalModels>;
  choose: (
    lane: string,
    model: string,
    expectedRevision: string,
  ) => Promise<AgentLocalModels>;
};

const same = (a: AgentListedModel | null, b: AgentListedModel | null) =>
  a !== null && b !== null && a.lane === b.lane && a.model === b.model;

/**
 * The stored lists and reading model, kept naming `wanted`: the model the
 * person selected, by catalogue lane id. Each wanted model is stored at most
 * once per revision read, so a refusal is not retried in a loop; a revision
 * another change moved is read again first. Null until the first read
 * answers, or where the host offers none.
 */
export function useReadingModel(
  host: ReadingModelHost | null,
  wanted: AgentListedModel | null,
  refreshVersion: number,
  reader: string | null,
): AgentLocalModels | null {
  const owner = useMemo(
    () => ({ host, reader, tried: new Set<string>() }),
    [host, reader],
  );
  const [held, setHeld] = useState<{
    owner: typeof owner;
    value: AgentLocalModels;
  } | null>(null);
  const stored = held?.owner === owner ? held.value : null;
  const [reads, setReads] = useState(0);
  const generation = useRef(0);
  useLayoutEffect(
    () => () => {
      generation.current += 1;
    },
    [owner],
  );
  useEffect(() => {
    const { host, reader } = owner;
    if (!host || reader === null) return;
    let current = true;
    const mine = generation.current;
    host.read().then(
      (value) => {
        if (current && mine === generation.current) setHeld({ owner, value });
      },
      () => {
        // Nothing read: the picker offers what the catalog lists.
      },
    );
    return () => {
      current = false;
    };
  }, [owner, reads, refreshVersion]);
  const wantedLane = wanted?.lane ?? null;
  const wantedModel = wanted?.model ?? null;
  useEffect(() => {
    const { host, reader, tried } = owner;
    if (!host || reader === null || stored?.state !== "readable") return;
    if (wantedLane === null || wantedModel === null) return;
    const chosen = { lane: wantedLane, model: wantedModel };
    if (same(stored.reading, chosen)) return;
    const attempt = `${wantedLane}\u0000${wantedModel}\u0000${stored.revision}`;
    if (tried.has(attempt)) return;
    tried.add(attempt);
    const mine = generation.current;
    // The answer is kept even when a later read lands first: it is what the
    // service stored last.
    host.choose(wantedLane, wantedModel, stored.revision).then(
      (value) => {
        if (mine === generation.current) setHeld({ owner, value });
      },
      (error: unknown) => {
        if (mine !== generation.current) return;
        // Another change came first: what is stored now is read again.
        if (failureCode(error) === "agent_local_models_revision_conflict")
          setReads((count) => count + 1);
      },
    );
  }, [owner, stored, wantedLane, wantedModel]);
  return host && reader !== null ? stored : null;
}
