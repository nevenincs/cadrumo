import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { ledgerFailure, type LedgerFailureCode } from "../../../shell/ledger";
import { modeloEditBody, type ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type {
  ModeloEditApplyPrerequisiteV1,
  ModeloEditReviewFindingV1,
  ModeloFormRebaseEntryV1,
} from "../../../shell/modeloContract/modeloEdit";
import type { ModeloEditApplyBaselineV1 } from "../../../shell/modeloContract/modeloEditWork";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import {
  editKey,
  editSubmission,
  renewBaseline,
  type FormSession,
} from "../form/session";
import { useModeloOperation } from "../WriteScope";
import { servedRefusal, type ServedRefusal } from "../../../shell/refusal";
import { mayRenew } from "./operationRun";

// The review's run: the staged edits are checked by a preflight on the
// admitted baseline, applied once, and followed until the apply settles. A
// stale baseline is renewed once, as the application allows only when nothing
// moved under it; either way the declaration is read again and the edits are
// checked on the baseline left, the renewed one or the one the new read
// admits, and that check says what became of each held edit. An apply
// refused only because its baseline went stale changed nothing, so its
// baseline is renewed once and the apply sent again: taking time over the
// review never refuses it. A renewal refused because the declaration moved
// checks the edits again instead of applying them. An
// apply whose settlement was not observed is unknown: it may have committed,
// so it is never sent again, and nothing more is applied until the
// operation finishes and the declaration is read again. Staged edits are cleared only by an apply the
// page saw settle.

export type ReviewPhase =
  | { kind: "checking" }
  | {
      kind: "checked";
      /** What the check found, worded, as the review lists it. */
      findings: ModeloEditReviewFindingV1[];
      /** Whether the declaration does not record which values the filer
       * typed, so applying returns the others to their source. */
      operatorEntriesUnknown: boolean;
    }
  /** The application refused the edits as they stand, and why. */
  | { kind: "refused"; words: string | null }
  /** The declaration moved again after it was read again: nothing more is
   * renewed or read until the filer asks to check again. */
  | { kind: "still_moving" }
  /** The check did not answer; nothing was changed. */
  | { kind: "check_failed"; code: LedgerFailureCode | "refused" }
  | { kind: "applying" }
  | { kind: "applied" }
  /** The apply was refused, or never reached the runtime; nothing was
   * changed and the edits are still staged. `words` is why, as the
   * application served it; null when it served none. `refusal` is the
   * served refusal with its stored verdict, for the window's one refusal
   * notice; null when the apply never reached the runtime. */
  | {
      kind: "not_applied";
      code: LedgerFailureCode | "refused";
      words: string | null;
      refusal: ServedRefusal | null;
    }
  /** The apply was sent and its settlement was not seen. */
  | { kind: "unknown"; operationId: string | null };

/** What a check came to, and what the application said became of each
 * held change, to apply to the read the check was made on. */
type Checked = {
  phase: ReviewPhase;
  report: ModeloFormRebaseEntryV1[] | null;
};

/** The refusal an apply settles with when its baseline went stale: nothing
 * was written, so it may be sent again on a renewed baseline. */
const BASELINE_STALE = "REFUSED_MODELO_EDIT_BASELINE_STALE";

/** What one renewal came to, for every check that waited on it. */
type Renewal = Promise<ReviewPhase | null>;

/** The preflight of the staged edits on `baseline`. A stale baseline is
 * renewed once, through `renew`; whatever the renewal comes to, a new check
 * follows on the declaration it leaves, and this one has nothing more to
 * say unless the renewal failed. */
async function preflight(
  port: ModeloPort,
  session: FormSession,
  baseline: ModeloEditApplyBaselineV1,
  language: OutputLanguage,
  movedBefore: boolean,
  renew: (baseline: ModeloEditApplyBaselineV1) => Renewal,
): Promise<Checked> {
  try {
    const outcome = await port.edit(
      "modelo.edit.preflight",
      modeloEditBody(
        editSubmission(baseline, session.staged.values(), language, true),
      ),
    );
    if (outcome.kind !== "settled")
      return { phase: { kind: "check_failed", code: "refused" }, report: null };
    const read = outcome.result;
    const answer = read.outcome;
    // What became of each held change is said only by a check that
    // evaluated them; a refused check says nothing about them.
    if (answer.outcome === "evaluated")
      return {
        phase: {
          kind: "checked",
          findings: read.findings,
          operatorEntriesUnknown: read.operator_entries_unknown,
        },
        report: read.rebase,
      };
    if (answer.refusal.kind !== "stale_edit_baseline")
      return {
        phase: { kind: "refused", words: read.refusal_words },
        report: null,
      };
    // Stale again on the baseline a renewal or a re-read left: the
    // declaration keeps moving, so this check stops, as the TUI's does.
    if (movedBefore) return { phase: { kind: "still_moving" }, report: null };
  } catch (error) {
    return {
      phase: { kind: "check_failed", code: ledgerFailure(error).code },
      report: null,
    };
  }
  const failed = await renew(baseline);
  return { phase: failed ?? { kind: "checking" }, report: null };
}

/** Renews a stale baseline, as the application allows it, and reads the
 * declaration again. A renewal succeeds only when nothing moved under the
 * baseline; when it is refused because something moved, the declaration is
 * read again and the held changes are checked on the baseline that read
 * admits, as the TUI does. Null when a new check is to follow; otherwise
 * the phase that says why it cannot. */
async function renewal(
  port: ModeloPort,
  baseline: ModeloEditApplyBaselineV1,
  language: OutputLanguage,
  onRenewed: (baseline: ModeloEditApplyBaselineV1) => void,
  onReread: () => Promise<boolean>,
): Promise<ReviewPhase | null> {
  const renewed = await renewBaseline(port, baseline, language);
  if (renewed.kind === "failed")
    return { kind: "check_failed", code: renewed.code };
  if (renewed.kind === "renewed") onRenewed(renewed.baseline);
  return (await onReread())
    ? null
    : { kind: "check_failed", code: "unavailable" };
}

export function useEditReview({
  open,
  envelope,
  session,
  port,
  language,
  onReread,
  onPrerequisiteHeld,
}: {
  open: boolean;
  envelope: ModeloWorkbenchFormProjectionV1;
  session: FormSession;
  port: ModeloPort;
  language: OutputLanguage;
  /** Reads the declaration again; false when the read failed. */
  onReread: () => Promise<boolean>;
  onPrerequisiteHeld?: (held: boolean) => void;
}) {
  const [phase, setPhase] = useState<ReviewPhase>({ kind: "checking" });
  const { holds, target, hold, run: runWrite } = useModeloOperation();
  const blocked = hold !== undefined;
  const alive = useRef(true);
  const checks = useRef(0);
  // The renewal under way, which every check that finds the baseline stale
  // meanwhile waits on instead of starting another.
  const renewing = useRef<Renewal | null>(null);
  // Whether the baseline was renewed or read again since the filer last
  // asked to check: a check stale again then stops instead of renewing.
  const moved = useRef(false);
  useLayoutEffect(() => {
    alive.current = true;
    const checkTickets = checks;
    return () => {
      alive.current = false;
      ++checkTickets.current;
    };
  }, [holds, target, port]);
  useLayoutEffect(() => {
    ++checks.current;
  }, [blocked]);

  // The session holds the one baseline the form's checks and applies share.
  const baseline = session.baseline;
  const check = useCallback(async () => {
    if (!alive.current || holds.blocking(target)) return;
    if (!baseline) {
      setPhase({ kind: "check_failed", code: "not_admitted" });
      return;
    }
    setPhase({ kind: "checking" });
    // Only the latest check speaks: a renewal starts another.
    const ticket = ++checks.current;
    const version = holds.admissionVersion(target);
    const answer = await preflight(
      port,
      session,
      baseline,
      language,
      moved.current,
      (stale) => {
        if (
          !alive.current ||
          holds.blocking(target) ||
          holds.admissionVersion(target) !== version
        )
          return Promise.resolve(null);
        const held = renewing.current;
        if (held) return held;
        if (
          !mayRenew({
            ticket,
            latest: checks.current,
            stale,
            current: current.current,
          })
        )
          return Promise.resolve(null);
        moved.current = true;
        const isCurrent = () =>
          alive.current &&
          ticket === checks.current &&
          !holds.blocking(target) &&
          holds.admissionVersion(target) === version;
        const running = renewal(
          port,
          stale,
          language,
          (next) => {
            if (isCurrent()) session.adoptBaseline(next);
          },
          () => (isCurrent() ? onReread() : Promise.resolve(false)),
        );
        renewing.current = running;
        void running.finally(() => {
          if (renewing.current === running) renewing.current = null;
        });
        return running;
      },
    );
    if (
      !alive.current ||
      ticket !== checks.current ||
      holds.blocking(target) ||
      holds.admissionVersion(target) !== version
    )
      return;
    // A check that evaluated the edits ends the moving: a later stale
    // baseline may be renewed again.
    if (answer.phase.kind === "checked") moved.current = false;
    // The report is of the read this check was made on, which is the read
    // the form holds while this check is the latest.
    if (answer.report?.some((entry) => entry.outcome !== "kept"))
      session.rebase(answer.report);
    setPhase(answer.phase);
  }, [baseline, port, session, language, onReread, holds, target]);

  // The baseline the review holds now, for a check that was overtaken.
  const current = useRef(baseline);
  useEffect(() => {
    current.current = baseline;
  });
  // Each opening starts as the TUI's review does: one renewal and re-read
  // are allowed again. Only the opening edge clears it, never a new
  // baseline.
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open && !wasOpen.current) moved.current = false;
    wasOpen.current = open;
  }, [open]);

  // Each opening checks the edits as they now stand. A shared write hold
  // prevents checks from rebasing edits while their write is unresolved.
  const latest = useRef(check);
  useEffect(() => {
    latest.current = check;
  });
  const editsKey = [...session.staged.keys()].join("\u0000");
  const baselineId = baseline?.baseline_id ?? null;
  const previousCheck = useRef<{
    open: boolean;
    blocked: boolean;
    editsKey: string;
    baselineId: string | null;
  } | null>(null);
  useEffect(() => {
    const before = previousCheck.current;
    previousCheck.current = { open, blocked, editsKey, baselineId };
    const sameInputs =
      before?.open === open &&
      before.editsKey === editsKey &&
      before.baselineId === baselineId;
    if (sameInputs && before.blocked === blocked) return;
    // Nothing staged, as after an apply, has nothing to check.
    if (!open || blocked || editsKey === "") return;
    // A definitive apply answer stays visible. Releasing its transient
    // running hold is not a request to replace it with another preflight.
    if (
      sameInputs &&
      before.blocked &&
      (phase.kind === "applying" ||
        phase.kind === "not_applied" ||
        phase.kind === "applied")
    )
      return;
    void latest.current();
  }, [open, blocked, editsKey, baselineId, phase.kind]);

  // A refused apply may name a source its box needs first; the worker holds
  // it for this window only, so it is read once, here, and stands while the
  // calculation it was named for is current and its box is not yet staged.
  const [prerequisite, setPrerequisite] = useState<{
    held: ModeloEditApplyPrerequisiteV1;
    read: ModeloWorkbenchFormProjectionV1;
  } | null>(null);
  const readPrerequisite = useCallback(
    async (on: ModeloEditApplyBaselineV1, operationId: string) => {
      setPrerequisite(null);
      if (
        on.current_calculation_revision_id !== envelope.calculation_revision_id
      )
        return;
      try {
        const outcome = await port.submit("modelo.edit.apply_prerequisite", {
          work_unit_id: envelope.work_unit_id,
          apply_operation_id: operationId,
          baseline_id: on.baseline_id,
          calculation_revision_id: on.current_calculation_revision_id,
          registry_revision_id: envelope.registry_revision_id,
          output_language: language,
        });
        const held =
          outcome.kind === "settled" ? outcome.result.prerequisite : null;
        if (held && alive.current) setPrerequisite({ held, read: envelope });
      } catch {
        // Without the read the refusal still stands as not applied.
      }
    },
    [port, envelope, language],
  );
  const heldField = prerequisite
    ? session.fieldAt({
        kind: "casilla",
        casilla_id: prerequisite.held.casilla_id,
      })
    : null;
  const standing =
    prerequisite !== null &&
    heldField !== null &&
    session.stagedCount > 0 &&
    envelope.form.form.edit_closure === null &&
    prerequisite.held.calculation_revision_id ===
      envelope.calculation_revision_id &&
    !session.staged.has(editKey(heldField));
  useEffect(() => {
    onPrerequisiteHeld?.(standing);
  }, [standing, onPrerequisiteHeld]);

  const apply = useCallback(async () => {
    if (!baseline || holds.blocking(target) || phase.kind !== "checked") return;
    ++checks.current;
    setPhase({ kind: "applying" });
    const send = (on: ModeloEditApplyBaselineV1) =>
      runWrite(
        () =>
          port.edit(
            "modelo.edit.apply",
            modeloEditBody(
              editSubmission(on, session.staged.values(), language),
            ),
          ),
        () => alive.current,
      );
    let on = baseline;
    let run = await send(on);
    if (run?.kind === "refused" && run.reason === BASELINE_STALE) {
      const renewal = await renewBaseline(port, on, language);
      if (!alive.current) return;
      if (renewal.kind === "moved") {
        // The declaration moved since the check: the edits are checked
        // again on it, and nothing is applied.
        moved.current = false;
        void check();
        return;
      }
      if (renewal.kind === "renewed") {
        on = renewal.baseline;
        run = await send(on);
      }
    }
    if (!run || !alive.current) return;
    if (run.kind === "settled" || run.kind === "saved_unread") {
      session.discardAll();
      if (alive.current) setPhase({ kind: "applied" });
      await onReread();
    } else if (run.kind === "refused") {
      if (alive.current)
        setPhase({
          kind: "not_applied",
          code: "refused",
          words: run.words,
          refusal: servedRefusal(run.words, run.detail),
        });
      await readPrerequisite(on, run.operationId);
    } else if (run.kind === "not_sent") {
      if (alive.current)
        setPhase({
          kind: "not_applied",
          code: run.code,
          words: null,
          refusal: null,
        });
    } else {
      if (alive.current)
        setPhase({ kind: "unknown", operationId: run.operationId });
    }
  }, [
    baseline,
    holds,
    target,
    runWrite,
    phase.kind,
    port,
    session,
    onReread,
    language,
    readPrerequisite,
    check,
  ]);

  return {
    phase:
      hold?.phase === "unknown"
        ? ({ kind: "unknown", operationId: hold.operationId } as const)
        : phase,
    blocked,
    apply,
    recheck: () => {
      // The filer asks again: one more renewal is allowed.
      moved.current = false;
      void check();
    },
    prerequisite:
      standing && prerequisite && heldField
        ? { field: heldField, words: prerequisite.held.words }
        : null,
  };
}
