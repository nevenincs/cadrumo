// The review and apply of what is staged, as the page runs it: the period is
// read again and every staged movement compared with how the page read it,
// the plan is built from that read, the apply runs once, and whatever did
// not save stays staged. A write whose outcome was not observed pauses
// every write until the person reads the ledger again; nothing is retried.

import { useCallback, useRef, useState } from "react";
import type {
  CatalogueInvoice,
  LedgerPort,
  LedgerRow,
} from "../../../shell/ledger";
import {
  changedSinceRead,
  resolveUnknown,
  runPlan,
  stageAfterApply,
  type ApplyReport,
  type StepReport,
  type UnknownResolution,
} from "../../../shell/ledgerApply";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import type { LedgerPlan, PlanStep } from "../../../shell/ledgerPlan";
import {
  stagedMovements,
  type StageEvent,
  type StageField,
  type StagedContent,
} from "../../../shell/ledgerStage";
import {
  readAnswer,
  readFailure,
  readWindow,
  rowsById,
  type LedgerReadFailure,
} from "../../../shell/ledgerWindow";
import { askedConflicts, type AskedConflict } from "./editingModel";

export type ReviewState =
  | { phase: "closed" }
  | { phase: "reading" }
  | { phase: "failed"; failure: LedgerReadFailure }
  | {
      phase: "ready";
      /** The stored rows as read now, which the plan is built from. */
      rows: Map<string, LedgerRow>;
      /** Movements changed elsewhere in a field the person changed, or
       * gone, still to be looked at. */
      conflicts: AskedConflict[];
      /** The invoices staged links name, read for the review. */
      invoices: CatalogueInvoice[] | null;
    }
  | {
      phase: "applying";
      plan: LedgerPlan;
      reports: StepReport[];
      rows: Map<string, LedgerRow>;
    }
  | {
      phase: "done";
      plan: LedgerPlan;
      report: ApplyReport;
      /** The rows read after the apply, for what was unchanged. */
      fresh: Map<string, LedgerRow> | null;
      rows: Map<string, LedgerRow>;
      /** When the readiness checks ran again. */
      checkedAt: number;
    };

/** A write whose outcome is unknown, and what was staged when it ran. */
export type Paused = { step: PlanStep; content: StagedContent };

/** What a re-read found of a paused write, movement by movement. */
export type UnknownFinding = { id: string; resolution: UnknownResolution };

/** Reads the rows of `ids` not in `rows` one by one, as the movements
 * staged outside the period shown. */
async function readMissing(
  port: LedgerPort,
  ids: readonly string[],
  rows: Map<string, LedgerRow>,
  read: ReadonlyMap<string, LedgerRow>,
): Promise<LedgerReadFailure | null> {
  for (const id of ids) {
    if (rows.has(id)) continue;
    try {
      const answer = readAnswer(
        await port.submit("ledger.view", { transaction_prefix: id }),
      );
      if (answer.kind === "failed") {
        // Not found is a movement that left: the plan says so.
        if (answer.failure.kind === "refused") continue;
        return answer.failure;
      }
      if (answer.result.transaction.transaction_id !== id) continue;
      rows.set(id, {
        transaction: answer.result.transaction,
        review_status: answer.result.review_status,
        group_label: read.get(id)?.group_label ?? null,
        own_account_id: read.get(id)?.own_account_id ?? null,
      });
    } catch (error) {
      return readFailure(error);
    }
  }
  return null;
}

/** Every staged movement, as stored now. */
async function readStaged(
  port: LedgerPort,
  period: LedgerPeriod | null,
  content: StagedContent,
  read: ReadonlyMap<string, LedgerRow>,
): Promise<
  | { kind: "read"; rows: Map<string, LedgerRow> }
  | { kind: "failed"; failure: LedgerReadFailure }
> {
  const answer = await readWindow(port, period);
  if (answer.kind === "failed") return answer;
  const rows = rowsById(answer.rows);
  const failure = await readMissing(
    port,
    [...stagedMovements(content)],
    rows,
    read,
  );
  return failure ? { kind: "failed", failure } : { kind: "read", rows };
}

/** The fields a step saves on each movement it names. */
export function stepFields(step: PlanStep): Map<string, StageField[]> {
  switch (step.kind) {
    case "bulk":
      return new Map(step.rows.map((row) => [row.transactionId, row.fields]));
    case "classify":
    case "update":
      return new Map([[step.transactionId, step.fields]]);
    default:
      return new Map();
  }
}

export function useLedgerApply({
  port,
  period,
  content,
  read,
  dispatch,
  afterApply,
}: {
  port: LedgerPort;
  period: LedgerPeriod | null;
  content: StagedContent;
  /** The rows as the page read them when the changes were staged. */
  read: () => ReadonlyMap<string, LedgerRow>;
  dispatch: (event: StageEvent) => void;
  /** Reads the window again, with the readiness checks after it, and
   * follows new ids. */
  afterApply: (
    report: ApplyReport,
    rows: ReadonlyMap<string, LedgerRow>,
  ) => void;
}) {
  const [state, setState] = useState<ReviewState>({ phase: "closed" });
  const [paused, setPaused] = useState<Paused | null>(null);
  const [findings, setFindings] = useState<UnknownFinding[] | null>(null);
  const [rereading, setRereading] = useState(false);
  const latest = useRef(content);
  latest.current = content;
  const asked = useRef(0);

  const open = useCallback(async () => {
    asked.current += 1;
    const mine = asked.current;
    setState({ phase: "reading" });
    const staged = latest.current;
    const before = read();
    const answer = await readStaged(port, period, staged, before);
    if (asked.current !== mine) return;
    if (answer.kind === "failed") {
      setState({ phase: "failed", failure: answer.failure });
      return;
    }
    const conflicts = askedConflicts(
      changedSinceRead(staged, before, answer.rows),
      staged,
    );
    let invoices: CatalogueInvoice[] | null = null;
    if (staged.actions.some((action) => action.kind === "link")) {
      try {
        const listed = readAnswer(await port.submit("ledger.invoice.list", {}));
        invoices = listed.kind === "answer" ? listed.result.invoices : null;
      } catch {
        invoices = null;
      }
    }
    if (asked.current !== mine) return;
    setState({ phase: "ready", rows: answer.rows, conflicts, invoices });
  }, [port, period, read]);

  const close = useCallback(() => {
    asked.current += 1;
    setState((current) =>
      current.phase === "applying" ? current : { phase: "closed" },
    );
  }, []);

  /** The person looked at a conflict and chose: theirs drops the staged
   * fields, mine keeps them over what is stored now. */
  const resolve = useCallback(
    (id: string, keep: "mine" | "theirs", fields: StageField[]) => {
      if (keep === "theirs")
        for (const field of fields)
          dispatch({ type: "revert_cell", id, field });
      setState((current) =>
        current.phase === "ready"
          ? {
              ...current,
              conflicts: current.conflicts.filter(
                (conflict) => conflict.transactionId !== id,
              ),
            }
          : current,
      );
    },
    [dispatch],
  );
  const resolveAll = useCallback(() => {
    setState((current) =>
      current.phase === "ready" ? { ...current, conflicts: [] } : current,
    );
  }, []);

  const apply = useCallback(
    async (plan: LedgerPlan) => {
      if (state.phase !== "ready" || paused) return;
      const rows = state.rows;
      const staged = latest.current;
      setState({ phase: "applying", plan, reports: [], rows });
      dispatch({ type: "apply_started" });
      const report = await runPlan(port, plan, (step) =>
        setState((current) =>
          current.phase === "applying"
            ? { ...current, reports: [...current.reports, step] }
            : current,
        ),
      );
      for (const event of stageAfterApply(staged, report)) dispatch(event);
      // The paused write is the one whose outcome was not observed, which
      // may be a write that followed an action rather than a planned one.
      const unobserved = report.steps.find(
        (step) =>
          step.outcome.kind === "unknown" ||
          step.outcome.kind === "saved_unread",
      );
      if (report.paused && unobserved)
        setPaused({ step: unobserved.step, content: staged });
      // What was unchanged is shown as stored, read again.
      const after = await readWindow(port, period);
      const fresh = after.kind === "read" ? rowsById(after.rows) : null;
      if (fresh) await readMissing(port, report.reread, fresh, rows);
      setState({
        phase: "done",
        plan,
        report,
        fresh,
        rows,
        checkedAt: Date.now(),
      });
      afterApply(report, fresh ?? rows);
    },
    [state, paused, port, period, dispatch, afterApply],
  );

  /** Reads the ledger after an unknown outcome and says, movement by
   * movement, whether the write saved. What saved leaves the stage; the
   * rest stays staged. */
  const reread = useCallback(async () => {
    if (!paused) return;
    setRereading(true);
    const answer = await readStaged(port, period, paused.content, read());
    setRereading(false);
    if (answer.kind === "failed") return;
    const found = resolveUnknown(paused.step, paused.content, answer.rows);
    const saved = stepFields(paused.step);
    for (const [id, resolution] of found) {
      if (resolution !== "saved") continue;
      for (const field of saved.get(id) ?? [])
        dispatch({ type: "revert_cell", id, field });
      const step = paused.step;
      if (step.kind === "action" || step.kind === "answer")
        dispatch({ type: "drop_action", id: step.action.id });
    }
    setFindings([...found].map(([id, resolution]) => ({ id, resolution })));
    setPaused(null);
    afterApply(
      {
        steps: [],
        paused: null,
        stopped: null,
        rekeys: [],
        reread: [],
        saved: 0,
      },
      answer.rows,
    );
  }, [paused, port, period, read, dispatch, afterApply]);

  return {
    state,
    open,
    close,
    resolve,
    resolveAll,
    apply,
    paused,
    reread,
    rereading,
    findings,
    dismissFindings: () => setFindings(null),
  };
}
