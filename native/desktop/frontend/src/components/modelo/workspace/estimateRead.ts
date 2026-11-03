import { useCallback, useEffect, useRef, useState } from "react";
import { formatAmount } from "../../../shared/numbers";
import type { LedgerOutcome } from "../../../shell/ledger";
import type { ModeloPort } from "../../../shell/modelo";
import type {
  ModeloProjectOperationProjection,
  PublicModeloFormField,
} from "../../../shell/modeloContract";
import type { OperationRun } from "../dialogs/operationRun";

// The estimate of the annual return from the quarterly declarations, asked
// for on request. The application words everything it says; this holds only
// what the person asked for and what came back.

/** The estimate, from not asked for to answered. */
export type EstimateRead =
  | { phase: "idle" }
  | { phase: "reading" }
  | { phase: "ready"; projection: ModeloProjectOperationProjection }
  /** The profile does not state the region the estimate is made for. */
  | { phase: "needs_region" }
  /** The application settled it without estimating, in its own words. */
  | { phase: "refused"; words: string | null }
  /** The request did not reach the application, or its answer was lost. */
  | { phase: "failed" };

/** Sends one write once, as the declaration's writes are sent. */
export type SendWrite = <Result>(
  send: () => Promise<LedgerOutcome<Result>>,
) => Promise<OperationRun<Result> | null>;

/**
 * The estimate of one declaration's year. `region` reads the region the
 * profile states for it, or null where it states none; `run` is the
 * workspace's one way to send a write.
 */
export function useEstimate({
  port,
  year,
  region,
  run,
}: {
  port: ModeloPort;
  year: number;
  region: (() => Promise<string | null>) | undefined;
  run: SendWrite;
}) {
  const [read, setRead] = useState<EstimateRead>({ phase: "idle" });
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const ask = useCallback(async () => {
    if (!region) return;
    setRead({ phase: "reading" });
    let ccaa: string | null;
    try {
      ccaa = await region();
    } catch {
      if (alive.current) setRead({ phase: "failed" });
      return;
    }
    if (!alive.current) return;
    if (!ccaa) {
      setRead({ phase: "needs_region" });
      return;
    }
    const outcome = await run(() =>
      port.submit("modelo.project", { year, ccaa }),
    );
    if (!alive.current) return;
    if (!outcome) setRead({ phase: "idle" });
    else if (outcome.kind === "settled")
      setRead({ phase: "ready", projection: outcome.result });
    else if (outcome.kind === "refused")
      setRead({ phase: "refused", words: outcome.words });
    else setRead({ phase: "failed" });
  }, [port, region, run, year]);
  return { read, ask: region ? ask : null };
}

/** The currency a register's figures are in. */
const CURRENCY = "EUR";

/** A box's figure in the estimate, in the form's own kind of value. */
export function estimateFigure(
  locale: string,
  field: PublicModeloFormField | null,
  value: string,
): string {
  return field?.data_type === "money"
    ? formatAmount(locale, value, { currency: CURRENCY })
    : value;
}

/** What the estimate gave one box, to be drawn beside the form's own words
 * for it; null where it gave none. */
export function observedValue(
  projection: ModeloProjectOperationProjection,
  box: string | null,
): string | null {
  if (!box) return null;
  return (
    projection.casilla_observations.find((row) => row.casilla_id === box)
      ?.value ?? null
  );
}
