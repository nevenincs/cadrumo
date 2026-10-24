// One ledger read the Documents section shows: asked once it is shown and
// again on request, with what was read kept on screen meanwhile. A failed
// read is said as failed, never as empty, and an answer to a read no longer
// asked is dropped. What it reads lives in this hook's memory and goes with
// the profile.

import { useCallback, useEffect, useRef, useState } from "react";
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
  const [read, setRead] = useState<Read<LedgerResult<D>>>({
    phase: "reading",
    value: null,
  });
  const [wanted, setWanted] = useState(0);
  // The page's re-read after a write it could not settle reads this again.
  const { round } = useWritePause();
  const asked = useRef(0);
  const held = useRef({ reader, key });
  const latest = useRef(payload);
  latest.current = payload;

  useEffect(() => {
    if (held.current.reader !== reader || held.current.key !== key) {
      held.current = { reader, key };
      setRead({ phase: "reading", value: null });
    }
    const asking = latest.current;
    if (!shown || reader === null || asking === null) return;
    asked.current += 1;
    const mine = asked.current;
    setRead((before) => ({
      phase: "reading",
      value: before.phase === "failed" ? null : before.value,
    }));
    void port
      .submit(definition, asking)
      .then((outcome) => {
        if (mine !== asked.current) return;
        const answer = readAnswer(outcome);
        setRead(
          answer.kind === "answer"
            ? { phase: "ready", value: answer.result }
            : { phase: "failed", failure: answer.failure, value: null },
        );
      })
      .catch((error: unknown) => {
        if (mine !== asked.current) return;
        setRead({ phase: "failed", failure: readFailure(error), value: null });
      });
  }, [port, reader, shown, definition, key, wanted, round]);

  const reread = useCallback(() => setWanted((count) => count + 1), []);
  return { read, reread };
}
