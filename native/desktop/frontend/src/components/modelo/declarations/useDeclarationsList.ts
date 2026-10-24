// The declarations list as the page reads it: whole, once the page is shown,
// in the page's language. A list already read is kept in the page's memory
// and shown again as it was, until something is written or the language
// changes; then it is read again. What it reads lives in memory only and
// goes with the profile.

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import { ledgerFailure, type LedgerFailure } from "../../../shell/ledger";
import type { ModeloPort } from "../../../shell/modelo";
import type {
  ModeloDeclarationsListProjectionV1,
  OutputLanguage,
} from "../../../shell/modeloContract";

export type DeclarationsRead =
  | { phase: "reading"; list: ModeloDeclarationsListProjectionV1 | null }
  | { phase: "ready"; list: ModeloDeclarationsListProjectionV1 }
  | { phase: "failed"; failure: LedgerFailure; list: null };

/** The list as last read, and whether a write since has left it stale. */
export type ListMemory = {
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
  const lastWanted = useRef(wanted);

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
    setRead((held) => ({
      phase: "reading",
      list: held.phase === "failed" ? null : held.list,
    }));
    void port
      .declarations(language)
      .then((list) => {
        if (mine !== generation.current) return;
        memory.current.list = list;
        memory.current.stale = false;
        setRead({ phase: "ready", list });
      })
      .catch((error: unknown) => {
        if (mine !== generation.current) return;
        delete memory.current.list;
        setRead({ phase: "failed", failure: ledgerFailure(error), list: null });
      });
  }, [port, reader, language, shown, wanted, memory]);

  /** Reads the list again; what was read stays shown meanwhile. */
  const reread = useCallback(() => setWanted((count) => count + 1), []);
  return { read, reread };
}
