// The declarations list as the page reads it: whole, once the page is shown,
// in the page's language. A list already read is kept in the page's memory
// and shown again as it was, until something is written or the language
// changes; then it is read again. What it reads lives in memory only and
// goes with the profile.

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import { ledgerFailure, type LedgerFailure } from "../../../shell/ledger";
import type { ModeloPort } from "../../../shell/modelo";
import {
  isCreationWriteKey,
  type ModeloWriteMemory,
} from "../../../shell/modeloWriteHolds";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloDeclarationsListProjectionV1 } from "../../../shell/modeloContract/modeloDeclarations";

export type DeclarationsRead =
  | { phase: "reading"; list: ModeloDeclarationsListProjectionV1 | null }
  | { phase: "ready"; list: ModeloDeclarationsListProjectionV1 }
  | { phase: "failed"; failure: LedgerFailure; list: null };

/** The list as last read, and whether a write since has left it stale. */
export type ListMemory = ModeloWriteMemory & {
  list?: ModeloDeclarationsListProjectionV1;
  stale?: boolean;
};

const keptFor = (memory: ListMemory, language: OutputLanguage) =>
  memory.list?.output_language === language && !memory.stale
    ? memory.list
    : null;

export function useDeclarationsList(
  port: ModeloPort,
  reader: string | null,
  language: OutputLanguage,
  shown: boolean,
  memory: RefObject<ListMemory>,
) {
  const [read, setRead] = useState<DeclarationsRead>(() => {
    const kept = keptFor(memory.current, language);
    return kept
      ? { phase: "ready", list: kept }
      : { phase: "reading", list: null };
  });
  const generation = useRef(0);
  const lastReader = useRef(reader);
  const [wanted, setWanted] = useState(0);
  const lastWanted = useRef<number | null>(wanted);

  // A reply cannot update shared list memory after its view has left.
  useLayoutEffect(
    () => () => {
      generation.current += 1;
    },
    [port, reader, language, shown, wanted, memory],
  );

  useEffect(() => {
    if (lastReader.current !== reader) {
      lastReader.current = reader;
      memory.current = {};
      setRead({ phase: "reading", list: null });
    }
    if (!shown || reader === null) return;
    const asked = lastWanted.current !== wanted;
    lastWanted.current = wanted;
    if (!asked && keptFor(memory.current, language)) return;
    generation.current += 1;
    const mine = generation.current;
    let settled = false;
    const writes = memory.current.writes;
    const completed =
      writes
        ?.snapshot()
        .filter(
          (hold) => hold.phase === "refresh" && isCreationWriteKey(hold.key),
        ) ?? [];
    setRead((held) => ({
      phase: "reading",
      list: held.phase === "failed" ? null : held.list,
    }));
    void port
      .declarations(language)
      .then((list) => {
        if (mine !== generation.current) return;
        settled = true;
        memory.current.list = list;
        memory.current.stale = false;
        setRead({ phase: "ready", list });
        completed.forEach((hold) => writes?.readCompleted(hold));
      })
      .catch((error: unknown) => {
        if (mine !== generation.current) return;
        settled = true;
        delete memory.current.list;
        setRead({ phase: "failed", failure: ledgerFailure(error), list: null });
      });
    return () => {
      // A hidden view must resume a refresh that never completed.
      if (!settled) lastWanted.current = null;
    };
  }, [port, reader, language, shown, wanted, memory]);

  /** Reads the list again; what was read stays shown meanwhile. */
  const reread = useCallback(() => {
    // Retire the old read as soon as a write requests fresh information.
    generation.current += 1;
    setWanted((count) => count + 1);
  }, []);
  return { read, reread };
}
