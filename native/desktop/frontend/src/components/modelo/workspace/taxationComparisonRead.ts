import { useCallback, useEffect, useRef, useState } from "react";
import type { LedgerErrorDetail } from "../../../shell/ledger";
import type { ModeloPort } from "../../../shell/modelo";
import type { ModeloTaxationComparisonProjection } from "../../../shell/modeloContract/modeloWork";
import { runOperation } from "../dialogs/operationRun";

// The comparison of joint and individual filing, asked for on request. The
// application works both out on the values the declaration holds and words
// everything it says; this holds only what the person asked for and what came
// back. A refusal carries the closed reason the application settled it with
// and, for boxes without a value, the boxes it names.

/** The comparison, from not asked for to answered. */
export type TaxationComparisonRead =
  | { phase: "idle" }
  | { phase: "reading" }
  | { phase: "ready"; projection: ModeloTaxationComparisonProjection }
  /** The application settled it without comparing, in its own words. */
  | {
      phase: "refused";
      /** The closed reason, or null when the refusal served none. */
      refusal: string | null;
      words: string | null;
      /** The boxes it names as without a value, in the order served. */
      boxes: string[];
    }
  /** The request did not reach the application, or its answer was lost. */
  | { phase: "failed" };

/** One fact the application served in a refusal's context. */
function served(detail: LedgerErrorDetail | null, key: string): string | null {
  const found = detail?.context.find((entry) => entry.key === key)?.value;
  return typeof found === "string" && found.trim() !== "" ? found : null;
}

/** The boxes a refusal names: the application lists their ids, comma
 * separated. */
function namedBoxes(detail: LedgerErrorDetail | null): string[] {
  return (served(detail, "casilla_ids") ?? "")
    .split(",")
    .map((box) => box.trim())
    .filter((box) => box !== "");
}

/** What a refusal came to, from the sentence and the detail it settled with. */
export function refusedRead(
  words: string | null,
  detail: LedgerErrorDetail | null,
): TaxationComparisonRead {
  return {
    phase: "refused",
    refusal: served(detail, "refusal"),
    words,
    boxes: namedBoxes(detail),
  };
}

/**
 * The comparison of one declaration. It is a read: it changes nothing, so it
 * holds no write of the declaration and asks for no new read of its form. A new
 * calculation of the declaration makes an earlier comparison out of date, so
 * `calculation` resets it.
 */
export function useTaxationComparison({
  port,
  workUnitId,
  calculation,
}: {
  port: ModeloPort;
  workUnitId: string;
  /** The calculation the declaration held when the form was read. */
  calculation: string | null;
}) {
  const [read, setRead] = useState<TaxationComparisonRead>({ phase: "idle" });
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  // An answer is the latest question's only: asking again, or the declaration
  // moving on, leaves an earlier question's answer unread.
  const latest = useRef(0);
  useEffect(() => {
    latest.current += 1;
    setRead({ phase: "idle" });
  }, [workUnitId, calculation]);
  const ask = useCallback(async () => {
    const ticket = ++latest.current;
    setRead({ phase: "reading" });
    const outcome = await runOperation(
      port,
      () =>
        port.submit("modelo.work.compare_taxation", {
          work_unit_id: workUnitId,
        }),
      () => alive.current,
    );
    if (!alive.current || ticket !== latest.current) return;
    if (outcome.kind === "settled")
      setRead({ phase: "ready", projection: outcome.result });
    else if (outcome.kind === "refused")
      setRead(refusedRead(outcome.words, outcome.detail));
    else setRead({ phase: "failed" });
  }, [port, workUnitId]);
  return { read, ask };
}
