import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
} from "react";
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import type { ApplyReport } from "../../../shell/ledgerApply";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import {
  actionRows,
  newDraft,
  stagedMovements,
  type StageEvent,
  type StageState,
} from "../../../shell/ledgerStage";
import type { WritePause } from "../WritePause";
import { ChangesTray } from "./ChangesTray";
import { stageTally } from "./editingModel";
import { LeaveDialog } from "./LeaveDialog";
import { ReviewDialog } from "./ReviewDialog";
import { useLedgerApply } from "./useLedgerApply";

/** Asks before staged work is dropped: true when it asked, and runs
 * `proceed` once the person chose to leave, or `stay` once they did not. */
export type LeaveGuard = (proceed: () => void, stay?: () => void) => boolean;

/**
 * The page's staged work as one whole: the stage store's events, with the
 * row each change was staged against; the tray; the review and apply,
 * which holds and settles through the page's write pause; and the guard
 * that asks before leaving drops what is staged.
 */
export function useLedgerEditing({
  port,
  period,
  rows,
  stage,
  dispatch,
  reread,
  onRekey,
  onShowRows,
  onGoToDraft,
  guardLeave,
  locale,
  pause,
  sealedOf,
}: {
  port: LedgerPort;
  period: LedgerPeriod | null;
  /** The stored rows the page shows now. */
  rows: readonly LedgerRow[] | null;
  stage: StageState;
  dispatch: Dispatch<StageEvent>;
  /** Reads the window again, and the readiness checks after it. */
  reread: () => void;
  /** A movement took a new id in an apply. */
  onRekey: (from: string, to: string) => void;
  onShowRows: (ids: string[]) => void;
  onGoToDraft: (key: string) => void;
  /** Hands the shell the guard its navigation, sign-out and close ask. */
  guardLeave?: (guard: LeaveGuard | null) => void;
  locale: string;
  /** The page's one write pause. */
  pause: WritePause;
  /** Which of `ids` a finalized declaration cites, read where not known. */
  sealedOf: (ids: readonly string[]) => Promise<ReadonlySet<string>>;
}) {
  const content = stage.content;
  const tally = useMemo(() => stageTally(content), [content]);

  // The row each staged movement was staged against, kept from the first
  // change: the apply compares it with the ledger as it is then.
  const base = useRef(new Map<string, LedgerRow>());
  const shown = useRef<ReadonlyMap<string, LedgerRow>>(new Map());
  useEffect(() => {
    shown.current = new Map(
      (rows ?? []).map((row) => [row.transaction.transaction_id, row]),
    );
  }, [rows]);
  const remember = useCallback((ids: Iterable<string>) => {
    for (const id of ids) {
      if (base.current.has(id)) continue;
      const row = shown.current.get(id);
      if (row) base.current.set(id, row);
    }
  }, []);
  const onStage = useCallback(
    (event: StageEvent) => {
      if (event.type === "stage") remember(event.cells.map((cell) => cell.id));
      if (event.type === "stage_action") remember(actionRows(event.action));
      dispatch(event);
    },
    [dispatch, remember],
  );
  const read = useCallback(() => {
    const out = new Map<string, LedgerRow>();
    for (const id of stagedMovements(content)) {
      const row = base.current.get(id) ?? shown.current.get(id);
      if (row) out.set(id, row);
    }
    return out;
  }, [content]);

  // What stays staged is now compared with the ledger as just read.
  const rebase = useCallback((fresh: ReadonlyMap<string, LedgerRow>) => {
    for (const [id, row] of fresh)
      if (base.current.has(id)) base.current.set(id, row);
  }, []);
  const afterApply = useCallback(
    (report: ApplyReport, fresh: ReadonlyMap<string, LedgerRow>) => {
      for (const { from, to } of report.rekeys) {
        base.current.delete(from);
        onRekey(from, to);
      }
      rebase(fresh);
      reread();
    },
    [onRekey, reread, rebase],
  );
  const apply = useLedgerApply({
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
  });

  const openReview = useCallback(() => {
    if (apply.paused || tally.units === 0) return;
    void apply.open();
  }, [apply, tally.units]);

  const addDraft = useCallback(() => {
    const draft = newDraft();
    dispatch({ type: "add_draft", draft });
    return draft.key;
  }, [dispatch]);

  // ---- Leaving -------------------------------------------------------------
  const [leaving, setLeaving] = useState<{
    proceed: () => void;
    stay?: () => void;
  } | null>(null);
  const staged = tally.units > 0;
  const guard = useRef<LeaveGuard>(() => false);
  guard.current = (proceed, stay) => {
    if (!staged) return false;
    setLeaving({ proceed, stay });
    return true;
  };
  useEffect(() => {
    if (!guardLeave) return;
    guardLeave((proceed, stay) => guard.current(proceed, stay));
    return () => guardLeave(null);
  }, [guardLeave]);
  // A browser asks on its own before a page with staged work unloads.
  useEffect(() => {
    if (!staged) return;
    const ask = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", ask);
    return () => window.removeEventListener("beforeunload", ask);
  }, [staged]);

  const dock = (
    <>
      {staged && (
        <ChangesTray
          tally={tally}
          paused={apply.paused}
          canUndo={stage.undo.length > 0}
          onUndo={() => dispatch({ type: "undo" })}
          onDiscard={() => dispatch({ type: "discard" })}
          onReview={openReview}
        />
      )}
      {apply.state.phase !== "closed" && (
        <ReviewDialog
          apply={apply}
          content={content}
          tally={tally}
          locale={locale}
          onStage={onStage}
          onShowRows={(ids) => {
            apply.close();
            onShowRows(ids);
          }}
          onGoToDraft={(key) => {
            apply.close();
            onGoToDraft(key);
          }}
        />
      )}
      {leaving && (
        <LeaveDialog
          units={tally.units}
          onCancel={() => {
            setLeaving(null);
            leaving.stay?.();
          }}
          onDiscard={() => {
            const { proceed } = leaving;
            setLeaving(null);
            dispatch({ type: "discard" });
            proceed();
          }}
          onReview={() => {
            setLeaving(null);
            leaving.stay?.();
            openReview();
          }}
        />
      )}
    </>
  );

  return {
    tally,
    onStage,
    openReview,
    addDraft,
    dock,
  };
}
