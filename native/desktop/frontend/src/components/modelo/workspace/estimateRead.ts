import { useCallback, useEffect, useRef, useState } from "react";
import { formatAmount, formatDecimal } from "../../../shared/numbers";
import {
  isProfileStep,
  type LedgerNextStep,
  type LedgerOutcome,
  type LedgerWorkStep,
} from "../../../shell/ledger";
import {
  calculateWorkRequest,
  createWorkRequest,
  type ModeloPort,
} from "../../../shell/modelo";
import type { ModeloProjectOperationProjection } from "../../../shell/modeloContract/modeloProject";
import type { PublicModeloFormField } from "../../../shell/modeloContract/modeloWorkForm";
import type { OperationRun } from "../dialogs/operationRun";

// The estimate of the annual return from the quarterly declarations, asked
// for on request. The application words everything it says; this holds only
// what the person asked for and what came back.

/** The estimate, from not asked for to answered. */
export type EstimateRead =
  | { phase: "idle" }
  | { phase: "reading" }
  | { phase: "ready"; projection: ModeloProjectOperationProjection }
  /** The application settled it without estimating, in its own words, and
   * perhaps naming the step that puts it right. */
  | { phase: "refused"; words: string | null; step: LedgerWorkStep | null }
  /** The request did not reach the application, or its answer was lost. */
  | { phase: "failed" };

/** Sends one write once, as the declaration's writes are sent. */
export type SendWrite = <Result>(
  send: () => Promise<LedgerOutcome<Result>>,
) => Promise<OperationRun<Result> | null>;

/** What the estimate shows once a step it offered has run: the step done
 * leaves it to be asked for again; a step refused says why and offers no
 * other. */
function afterStep<Result>(
  outcome: OperationRun<Result> | null,
  succeeded: (result: Result) => boolean,
): EstimateRead {
  if (!outcome || outcome.kind === "saved_unread") return { phase: "idle" };
  if (outcome.kind === "settled")
    return succeeded(outcome.result)
      ? { phase: "idle" }
      : { phase: "refused", words: null, step: null };
  if (outcome.kind === "refused")
    return { phase: "refused", words: outcome.words, step: null };
  return { phase: "failed" };
}

/** The step, where this window can do what it names; opening another
 * declaration needs the shell to open it, and a step naming a profile detail
 * is not this surface's to offer. */
function runnable(
  step: LedgerNextStep | null,
  open: ((workUnitId: string) => void) | undefined,
): LedgerWorkStep | null {
  if (step === null || isProfileStep(step)) return null;
  return step.kind === "open_work" && open === undefined ? null : step;
}

/**
 * The estimate of one declaration's year. `projectable` is the form's own
 * statement that the application can estimate this declaration; `run` is the
 * workspace's one way to send a write. The region is the application's to
 * resolve from the profile, so none is sent. `open` opens another declaration
 * in the shell, where a step names one whose own form says what it lacks; a
 * window with no way to open it is not offered that step.
 */
export function useEstimate({
  port,
  year,
  projectable,
  run,
  open,
}: {
  port: ModeloPort;
  year: number;
  projectable: boolean;
  run: SendWrite;
  open?: (workUnitId: string) => void;
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
    setRead({ phase: "reading" });
    const outcome = await run(() => port.submit("modelo.project", { year }));
    if (!alive.current) return;
    if (!outcome) setRead({ phase: "idle" });
    else if (outcome.kind === "settled")
      setRead({ phase: "ready", projection: outcome.result });
    else if (outcome.kind === "refused")
      setRead({
        phase: "refused",
        words: outcome.words,
        step: runnable(outcome.step, open),
      });
    else setRead({ phase: "failed" });
  }, [port, run, year, open]);
  // The step the application named, run as the window runs it anywhere else.
  // Once it has settled the estimate is asked for again, not shown stale.
  const take = useCallback(
    async (step: LedgerWorkStep) => {
      if (step.kind === "open_work") {
        // Nothing is sent: the declaration's own form says what it lacks, and
        // the shell opens it.
        open?.(step.work_unit_id);
        return;
      }
      setRead({ phase: "reading" });
      const next =
        step.kind === "create_work"
          ? afterStep(
              await run(() =>
                port.submit("modelo.work.create", createWorkRequest(step)),
              ),
              (result) => result.outcome.kind === "success",
            )
          : afterStep(
              await run(() =>
                port.submit(
                  "modelo.work.calculate",
                  calculateWorkRequest(step.work_unit_id),
                ),
              ),
              () => true,
            );
      if (alive.current) setRead(next);
    },
    [port, run, open],
  );
  return {
    read,
    ask: projectable ? ask : null,
    take: projectable ? take : null,
  };
}

/** The currency a register's figures are in. */
const CURRENCY = "EUR";

/** A box's figure in the estimate, in the form's own kind of value. */
export function estimateFigure(
  locale: string,
  field: PublicModeloFormField | null,
  value: string,
): string {
  switch (field?.data_type) {
    case "money":
      return formatAmount(locale, value, { currency: CURRENCY });
    case "decimal":
      return formatDecimal(locale, value, { minFraction: 2 });
    default:
      return value;
  }
}

/** One figure the estimate gives with the name the application served for it. */
export type EstimateFigure = { id: string; label: string; value: string };

function named<Key extends string>(
  group: string,
  values: Record<NoInfer<Key>, string>,
  words: Record<Key, string>,
): EstimateFigure[] {
  return (Object.keys(words) as Key[]).map((key) => ({
    id: `${group}.${key}`,
    label: words[key],
    value: values[key],
  }));
}

/** The figures of the estimate, each under the name the application served
 * for it: the quarterly declarations' totals, then the projected return's. */
export function estimateFigures(
  projection: ModeloProjectOperationProjection,
): EstimateFigure[] {
  return [
    ...named(
      "quarterly",
      projection.m130_accumulated,
      projection.m130_accumulated.words,
    ),
    ...named(
      "annual",
      projection.m100_projection,
      projection.m100_projection.words,
    ),
  ];
}

/** An amount of the estimate, in the window's language. */
export function estimateAmount(locale: string, value: string): string {
  return formatAmount(locale, value, { currency: CURRENCY });
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
