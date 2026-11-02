// One ledger read the Documents section shows: asked once it is shown and
// again on request, with what was read kept on screen meanwhile. A failed
// read is said as failed, never as empty, and an answer to a read no longer
// asked is dropped. What it reads lives in this hook's memory and goes with
// the profile.

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  LedgerDefinitionId,
  LedgerPort,
  LedgerRequest,
  LedgerResult,
} from "../../../shell/ledger";
import {
  readAnswer,
  readFailure,
  type LedgerReadFailure,
} from "../../../shell/ledgerWindow";
import { useWritePause } from "../WritePause";

export type Read<T> =
  | { phase: "reading"; value: T | null }
  | { phase: "ready"; value: T }
  | { phase: "failed"; failure: LedgerReadFailure; value: null };

/** Reads `definition` with `payload` while `shown`; `key` names the
 * payload, so a new key reads again. */
export function useLedgerRead<D extends LedgerDefinitionId>(
  port: LedgerPort,
  reader: string | null,
  shown: boolean,
  definition: D,
  payload: LedgerRequest<D> | null,
  key = "",
): { read: Read<LedgerResult<D>>; reread(): void } {
  const available = payload !== null;
  const identity = useMemo(
    () => ({ port, reader, definition, key, available }),
    [port, reader, definition, key, available],
  );
  const [stored, setStored] = useState<{
    identity: typeof identity;
    read: Read<LedgerResult<D>>;
  }>({ identity, read: { phase: "reading", value: null } });
  const [wanted, setWanted] = useState(0);
  // The page's re-read after a write it could not settle reads this again.
  const { round } = useWritePause();
  const latest = useRef(payload);
  latest.current = payload;
  const generation = useRef(0);
  // A hidden or replaced view stops accepting replies at commit, before passive cleanup.
  useLayoutEffect(
    () => () => {
      generation.current += 1;
    },
    [identity, shown],
  );

  useEffect(() => {
    const { port, reader, definition } = identity;
    const asking = latest.current;
    if (!shown || reader === null || asking === null) {
      setStored((before) =>
        before.identity === identity
          ? before
          : { identity, read: { phase: "reading", value: null } },
      );
      return;
    }
    let active = true;
    const mine = generation.current;
    setStored((before) => ({
      identity,
      read: {
        phase: "reading",
        value:
          before.identity === identity && before.read.phase !== "failed"
            ? before.read.value
            : null,
      },
    }));
    void port
      .submit(definition, asking)
      .then((outcome) => {
        if (!active || mine !== generation.current) return;
        const answer = readAnswer(outcome);
        setStored({
          identity,
          read:
            answer.kind === "answer"
              ? { phase: "ready", value: answer.result }
              : { phase: "failed", failure: answer.failure, value: null },
        });
      })
      .catch((error: unknown) => {
        if (!active || mine !== generation.current) return;
        setStored({
          identity,
          read: { phase: "failed", failure: readFailure(error), value: null },
        });
      });
    return () => {
      active = false;
    };
  }, [identity, shown, wanted, round]);

  const reread = useCallback(() => setWanted((count) => count + 1), []);
  const read: Read<LedgerResult<D>> =
    reader !== null && available && stored.identity === identity
      ? stored.read
      : { phase: "reading", value: null };
  return { read, reread };
}
