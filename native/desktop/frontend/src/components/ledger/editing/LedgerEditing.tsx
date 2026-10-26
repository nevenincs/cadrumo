import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
} from "react";
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import { releaseReview, type ApplyReport } from "../../../shell/ledgerApply";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import {
  actionRows,
  newDraft,
  stagedMovements,
  type StageEvent,
  type StageState,
} from "../../../shell/ledgerStage";
import { useNavigationGuard } from "../../../shell/navigation/hooks";
import type { SealedProgress, SealedRead } from "../useSealedMovements";
import type { WritePause } from "../WritePause";
import { ChangesTray } from "./ChangesTray";
import { stageTally } from "./editingModel";
import { LeaveDialog } from "./LeaveDialog";
import { ReviewDialog } from "./ReviewDialog";
import { useLedgerApply } from "./useLedgerApply";

/** Asks before staged work is dropped: true when it asked, and runs
 * `proceed` once the person chose to leave, or `stay` once they did not.
 * The shell registers an owner's guard of this shape as dirty work of the
 * page it was shown on. */
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
  locale,
  pause,
  sealedOf,
  returnFocus,
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
  locale: string;
  /** The page's one write pause. */
  pause: WritePause;
  /** Which of `ids` a finalized declaration cites, read where not known. */
  sealedOf: (
    ids: readonly string[],
    progress?: SealedProgress,
  ) => Promise<SealedRead>;
  /** Puts the focus back on the grid's active cell: false where the page
   * draws no grid. */
  returnFocus?: () => boolean;
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

  // A staged model answer that leaves the stage unanswered, wherever it
  // was dropped (the review, the tray, the leave guard, undo or a row's ×),
  // cancels its review, so it does not hold its movement at its review
  // step; so does leaving the page, which drops the stage. One whose answer
  // was sent is a write, and is left to settle.
  const staging = useRef<ReadonlyMap<string, string>>(new Map());
  const portRef = useRef(port);
  portRef.current = port;
  useEffect(() => {
    const now = new Map(
      content.actions.flatMap((action) =>
        action.kind === "suggestion"
          ? [[action.operationId, action.transactionId] as const]
          : [],
      ),
    );
    for (const [operation, movement] of staging.current)
      if (!now.has(operation))
        void releaseReview(portRef.current, operation, movement);
    staging.current = now;
  }, [content.actions]);
  useEffect(
    () => () => {
      for (const [operation, movement] of staging.current)
        void releaseReview(portRef.current, operation, movement);
      staging.current = new Map();
    },
    [],
  );

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

  // The review mounts only while open, so it has no trigger to hand the
  // focus back to: it goes to the grid's active cell, or else to what had
  // it when the review opened.
  const reviewOpener = useRef<HTMLElement | null>(null);
  const openReview = useCallback(() => {
    if (apply.paused || tally.units === 0) return;
    reviewOpener.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    void apply.open();
  }, [apply, tally.units]);
  const returnReviewFocus = (event: Event) => {
    event.preventDefault();
    const opener = reviewOpener.current;
    reviewOpener.current = null;
    // What the review led to, such as showing rows, keeps the focus.
    const active = document.activeElement;
    if (active !== null && active !== document.body) return;
    if (returnFocus?.()) return;
    if (opener?.isConnected) opener.focus();
  };

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
  // The page's staged work is dirty work of the Ledger: leaving the page, a
  // sign-out, a profile switch or the window's close asks here first.
  useNavigationGuard("ledger", staged ? "dirty" : "clean", {
    ask: (proceed, stay) => {
      if (!staged) return false;
      setLeaving({ proceed, stay });
      return true;
    },
    discard: () => dispatch({ type: "discard" }),
  });
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
          onCloseAutoFocus={returnReviewFocus}
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
