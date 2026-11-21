import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { failureCode } from "../errors";
import type {
  LocalModelListEntry,
  LocalModelListStatus,
} from "./localModelsContract";

// The model documents are read with is the one the person selected in the
// agent's model picker. The picker keeps that choice in the window; the agent
// service keeps it beside the local model lists, where a tax worker's reading
// finds it. This keeps the service's copy the picker's, and reads the lists
// the picker offers local models from.

/** Reading and storing the model documents are read with, as the host offers it. */
export type ReadingModelHost = {
  read: () => Promise<LocalModelListStatus>;
  choose: (
    lane: string,
    model: string,
    expectedRevision: string,
  ) => Promise<LocalModelListStatus>;
};

/** The stored lists and reading model as read, with the refusal of the last
 * read where it did not answer, and the way to read them again. */
export type ReadingModelRead = {
  /** Null until a read answers, or where the host offers none. */
  stored: LocalModelListStatus | null;
  /** The refusal of the newest read, null once one answers. */
  failure: string | null;
  retry: () => void;
};

const same = (a: LocalModelListEntry | null, b: LocalModelListEntry | null) =>
  a !== null && b !== null && a.lane === b.lane && a.model === b.model;

/**
 * The stored lists and reading model, kept naming `wanted`: the model the
 * person selected, by catalogue lane id. Each wanted model is stored at most
 * once per revision read, so a refusal is not retried in a loop; a revision
 * another change moved is read again first. A read that does not answer is
 * kept as its refusal, which the picker says, rather than left as if nothing
 * had been asked.
 */
export function useReadingModel(
  host: ReadingModelHost | null,
  wanted: LocalModelListEntry | null,
  refreshVersion: number,
  reader: string | null,
): ReadingModelRead {
  const owner = useMemo(
    () => ({ host, reader, tried: new Set<string>() }),
    [host, reader],
  );
  const [held, setHeld] = useState<{
    owner: typeof owner;
    value: LocalModelListStatus;
  } | null>(null);
  const stored = held?.owner === owner ? held.value : null;
  const [refused, setRefused] = useState<{
    owner: typeof owner;
    code: string;
  } | null>(null);
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
        if (current && mine === generation.current) {
          setHeld({ owner, value });
          setRefused(null);
        }
      },
      (error: unknown) => {
        if (current && mine === generation.current)
          setRefused({ owner, code: failureCode(error) });
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
    if (!host || reader === null || stored?.unreadable !== false) return;
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
  const offered = host !== null && reader !== null;
  return {
    stored: offered ? stored : null,
    failure: offered && refused?.owner === owner ? refused.code : null,
    retry: useCallback(() => setReads((count) => count + 1), []),
  };
}
