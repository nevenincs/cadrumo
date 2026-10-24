import { useEffect, useRef, useState } from "react";
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

// The inspector's reads of one movement: each is asked for only when its
// section is shown, held in this component's memory for the movement and
// the window's read it belongs to, and asked again when either changes.

export type InspectorRead<Result> =
  | { kind: "reading" }
  | { kind: "ready"; result: Result }
  | { kind: "failed"; failure: LedgerReadFailure };

/**
 * Reads `definition` with `request` while `wanted` holds, once per `key`:
 * the movement it is about with the generation of the window it was read
 * in, so a saved change reads it again. Null while it is not wanted.
 */
export function useLedgerRead<D extends LedgerDefinitionId>(
  port: LedgerPort,
  definition: D,
  request: LedgerRequest<D> | null,
  key: string,
  wanted: boolean,
): InspectorRead<LedgerResult<D>> | null {
  const [state, setState] = useState<{
    key: string;
    read: InspectorRead<LedgerResult<D>>;
  } | null>(null);
  // The request is named by the key; its object is new on every render.
  const latest = useRef(request);
  useEffect(() => {
    latest.current = request;
  });
  const on = wanted && request !== null;
  const held = state?.key === key ? state.read : null;
  const answered = held !== null && held.kind !== "reading";
  useEffect(() => {
    const payload = latest.current;
    if (!on || answered || payload === null) return;
    let active = true;
    setState({ key, read: { kind: "reading" } });
    void (async () => {
      let read: InspectorRead<LedgerResult<D>>;
      try {
        const answer = readAnswer(await port.submit(definition, payload));
        read =
          answer.kind === "answer"
            ? { kind: "ready", result: answer.result as LedgerResult<D> }
            : { kind: "failed", failure: answer.failure };
      } catch (error) {
        read = { kind: "failed", failure: readFailure(error) };
      }
      if (active) setState({ key, read });
    })();
    return () => {
      active = false;
    };
  }, [port, definition, key, on, answered]);
  return wanted ? (held ?? { kind: "reading" }) : null;
}
