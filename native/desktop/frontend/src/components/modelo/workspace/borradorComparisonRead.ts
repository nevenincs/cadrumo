import { useCallback, useEffect, useRef, useState } from "react";
import type { BorradorComparison, BorradorPort } from "../../../shell/borrador";
import { ledgerFailure } from "../../../shell/ledger";

// The year's AEAT draft beside the saved calculation, asked for on request.
// The application compares box by box and words every status, classification
// and reason; this holds only what the person asked for and what came back.
// The read reaches no network and changes nothing.

/** The comparison, from not asked for to answered. */
export type BorradorComparisonRead =
  | { phase: "idle" }
  | { phase: "reading" }
  | { phase: "ready"; comparison: BorradorComparison }
  /** The read did not answer; `code` is the host's closed reason. */
  | { phase: "failed"; code: string };

/**
 * The comparison for one profile's filing year, in `language`. A new
 * calculation of the declaration, or another year or language, makes an
 * earlier comparison out of date, so `calculation` resets it.
 */
export function useBorradorComparison({
  port,
  profile,
  year,
  language,
  calculation,
}: {
  port: BorradorPort;
  profile: string;
  year: number;
  language: string;
  /** The calculation the declaration held when the form was read. */
  calculation: string | null;
}) {
  const [read, setRead] = useState<BorradorComparisonRead>({ phase: "idle" });
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  // An answer is the latest question's only.
  const latest = useRef(0);
  useEffect(() => {
    latest.current += 1;
    setRead({ phase: "idle" });
  }, [profile, year, language, calculation]);
  const ask = useCallback(async () => {
    const ticket = ++latest.current;
    setRead({ phase: "reading" });
    try {
      const comparison = await port.compare(profile, year, language);
      if (alive.current && ticket === latest.current)
        setRead({ phase: "ready", comparison });
    } catch (error) {
      if (alive.current && ticket === latest.current)
        setRead({ phase: "failed", code: ledgerFailure(error).code });
    }
  }, [port, profile, year, language]);
  return { read, ask };
}
