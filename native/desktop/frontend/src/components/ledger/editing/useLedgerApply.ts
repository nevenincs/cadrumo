// The review and apply of what is staged, as the page runs it: the period is
// read again and every staged movement compared with how the page read it,
// the plan is built from that read, the apply runs once, and whatever did
// not save stays staged. A write whose outcome was not observed pauses
// every write on the page until the person reads the ledger again; nothing
// is retried.

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
} from "../../../shell/ledgerApply";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import type { LedgerPlan, PlanStep } from "../../../shell/ledgerPlan";
import {
  actionRows,
  stagedMovements,
  type StageEvent,
  type StageField,
  type StagedContent,
  type StagedValue,
} from "../../../shell/ledgerStage";
import {
  readAnswer,
  readFailure,
  readWindow,
  rowsById,
  type LedgerReadFailure,
} from "../../../shell/ledgerWindow";
import { useStrings, type Translate } from "../../../shell/strings";
import type { SealedRead } from "../useSealedMovements";
import type { WritePause } from "../WritePause";
import { askedConflicts, type AskedConflict } from "./editingModel";
import { actionText } from "./ReviewDialog";

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
      /** The invoices staged links name, read for the review; null where
       * the catalogue could not be read. */
      invoices: CatalogueInvoice[] | null;
      /** The staged movements a finalized declaration cites, as read. */
      sealed: ReadonlySet<string>;
      /** The staged movements whose sealed state could not be read: held
       * back until a read answers for them. */
      unread: ReadonlySet<string>;
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

/** The name of a movement or new movement, as the page shows it. */
function movementName(
  id: string,
  rows: ReadonlyMap<string, LedgerRow>,
  content: StagedContent,
): string {
  return (
    rows.get(id)?.transaction.description ||
    content.drafts.find((draft) => draft.key === id)?.fields.description ||
    id.slice(0, 12)
  );
}

/** What a step whose outcome is unknown wrote, in words: its movement
 * where it names one. */
function stepName(
  t: Translate,
  step: PlanStep,
  rows: ReadonlyMap<string, LedgerRow>,
  content: StagedContent,
): string {
  const ids =
    step.kind === "bulk"
      ? step.rows.map((row) => row.transactionId)
      : step.kind === "classify" || step.kind === "update"
        ? [step.transactionId]
        : step.kind === "add"
          ? [step.draftKey]
          : actionRows(step.action);
  return ids.length === 1
    ? movementName(ids[0]!, rows, content)
    : t("desktop.ledger.paused.staged");
}

/** Reads the catalogue for the invoices staged links name; null where it
 * could not be read. */
async function readInvoices(
  port: LedgerPort,
): Promise<CatalogueInvoice[] | null> {
  try {
    const listed = readAnswer(await port.submit("ledger.invoice.list", {}));
    return listed.kind === "answer" ? listed.result.invoices : null;
  } catch {
    return null;
  }
}

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

/** Whether two staged values are the same change. */
function sameValue(
  left: StagedValue | undefined,
  right: StagedValue | undefined,
): boolean {
  if (!left || !right) return left === right;
  return (
    left.kind === right.kind &&
    (left.kind === "clear" ||
      (right.kind === "set" && left.value === right.value))
  );
}

/** Whether two plain staged records hold the same content, whatever the
 * order their keys were written in. */
function sameJson(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (
    typeof left !== "object" ||
    typeof right !== "object" ||
    left === null ||
    right === null ||
    Array.isArray(left) !== Array.isArray(right)
  )
    return false;
  const a = left as Record<string, unknown>;
  const b = right as Record<string, unknown>;
  const keys = Object.keys(a).filter((key) => a[key] !== undefined);
  const others = Object.keys(b).filter((key) => b[key] !== undefined);
  return (
    keys.length === others.length &&
    keys.every((key) => sameJson(a[key], b[key]))
  );
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
  rebase,
  pause,
  sealedOf,
  locale,
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
  /** Compares what stays staged with the rows a re-read found. */
  rebase: (rows: ReadonlyMap<string, LedgerRow>) => void;
  /** The page's one write pause. */
  pause: WritePause;
  /** Which of `ids` a finalized declaration cites, read where not known. */
  sealedOf: (ids: readonly string[]) => Promise<SealedRead>;
  locale: string;
}) {
  const t = useStrings();
  const [state, setState] = useState<ReviewState>({ phase: "closed" });
  const paused = pause.held;
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
    const invoices = staged.actions.some((action) => action.kind === "link")
      ? await readInvoices(port)
      : [];
    const { sealed, unread } = await sealedOf([...stagedMovements(staged)]);
    if (asked.current !== mine) return;
    setState({
      phase: "ready",
      rows: answer.rows,
      conflicts,
      invoices,
      sealed,
      unread,
    });
  }, [port, period, read, sealedOf]);

  /** Reads again the sealed state the review could not read. */
  const rereadSealed = useCallback(async () => {
    if (state.phase !== "ready" || state.unread.size === 0) return;
    const mine = asked.current;
    const found = await sealedOf([...state.unread]);
    if (asked.current !== mine) return;
    setState((current) =>
      current.phase === "ready"
        ? {
            ...current,
            sealed: new Set([...current.sealed, ...found.sealed]),
            unread: found.unread,
          }
        : current,
    );
  }, [state, sealedOf]);

  /** Reads the catalogue again where the review could not read it. */
  const rereadInvoices = useCallback(async () => {
    const mine = asked.current;
    const invoices = await readInvoices(port);
    if (asked.current !== mine) return;
    setState((current) =>
      current.phase === "ready" ? { ...current, invoices } : current,
    );
  }, [port]);

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

  /** Drops from the stage what `step` was found to have saved on `id`,
   * which `sent` is the stage it was sent from: staged again, it would be
   * a change to the value already stored. A value or an action staged
   * again since, while writes were paused, is the person's newer change
   * and stays. */
  const dropSaved = useCallback(
    (step: PlanStep, id: string, sent: StagedContent) => {
      const now = latest.current;
      for (const field of stepFields(step).get(id) ?? [])
        if (sameValue(now.rows[id]?.[field], sent.rows[id]?.[field]))
          dispatch({ type: "revert_cell", id, field });
      if (step.kind !== "action" && step.kind !== "answer") return;
      // A re-staged approval keeps its id, so its content tells it apart.
      const staged = now.actions.find((action) => action.id === step.action.id);
      if (staged && sameJson(staged, step.action))
        dispatch({ type: "drop_action", id: step.action.id });
    },
    [dispatch],
  );

  const settle = useCallback(
    async (
      step: PlanStep,
      staged: StagedContent,
      seen: ReadonlySet<string>,
    ): Promise<string[] | null> => {
      const answer = await readStaged(port, period, staged, read());
      if (answer.kind === "failed") return null;
      const found = resolveUnknown(step, staged, answer.rows);
      // What the read after the apply saw saved was saved, whatever changed
      // it since.
      for (const id of seen) found.set(id, "saved");
      for (const [id, resolution] of found)
        if (resolution === "saved") dropSaved(step, id, staged);
      rebase(answer.rows);
      // A rules apply is keyed by its action, which is worded.
      const nameOf = (id: string) => {
        const action = staged.actions.find((found) => found.id === id);
        return action
          ? actionText(t, locale, action)
          : movementName(id, answer.rows, staged);
      };
      return [...found].map(([id, resolution]) =>
        t(`desktop.ledger.paused.found_${resolution}`, {
          movement: nameOf(id),
        }),
      );
    },
    [port, period, read, dropSaved, rebase, t, locale],
  );

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
      const seen = new Set<string>();
      if (report.paused && unobserved) {
        const step = unobserved.step;
        pause.hold({
          what: stepName(t, step, rows, staged),
          outcome:
            unobserved.outcome.kind === "saved_unread"
              ? "saved_unread"
              : "unknown",
          settle: () => settle(step, staged, seen),
        });
      }
      // What was unchanged is shown as stored, read again.
      const after = await readWindow(port, period);
      const fresh = after.kind === "read" ? rowsById(after.rows) : null;
      if (fresh) await readMissing(port, report.reread, fresh, rows);
      // A held write this read already shows saved leaves the stage now, so
      // no staged value stands equal to the stored one. Writes stay paused
      // until the person's re-read, which reports it as saved.
      if (report.paused && unobserved && fresh)
        for (const [id, resolution] of resolveUnknown(
          unobserved.step,
          staged,
          fresh,
        ))
          if (resolution === "saved") {
            seen.add(id);
            dropSaved(unobserved.step, id, staged);
          }
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
    [
      state,
      paused,
      port,
      period,
      dispatch,
      afterApply,
      pause,
      t,
      settle,
      dropSaved,
    ],
  );

  return {
    state,
    open,
    close,
    resolve,
    resolveAll,
    apply,
    paused,
    rereadInvoices,
    rereadSealed,
  };
}
