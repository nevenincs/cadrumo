import { useCallback, useEffect, useRef, useState } from "react";
import { ledgerFailure, type LedgerFailureCode } from "../../../shell/ledger";
import { modeloEditBody, type ModeloPort } from "../../../shell/modelo";
import type {
  ModeloEditApplyBaselineV1,
  ModeloEditApplyPrerequisiteV1,
  ModeloEditReviewFindingV1,
  ModeloFormRebaseEntryV1,
  ModeloWorkbenchFormProjectionV1,
  OutputLanguage,
} from "../../../shell/modeloContract";
import { editKey, editSubmission, type FormSession } from "../form/session";
import { runOperation } from "./operationRun";

// The review's run: the staged edits are checked by a preflight on the
// admitted baseline, applied once, and followed until the apply settles. A
// stale baseline is renewed once: the edits it keeps are staged again on the
// declaration as it is read next, and checked again on the renewed baseline. An
// apply whose settlement was not observed is unknown: it may have committed,
// so it is never sent again, and nothing more is applied until the
// declaration is read again. Staged edits are cleared only by an apply the
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
  /** The check did not answer; nothing was changed. */
  | { kind: "check_failed"; code: LedgerFailureCode | "refused" }
  | { kind: "applying" }
  | { kind: "applied" }
  /** The apply was refused, or never reached the runtime; nothing was
   * changed and the edits are still staged. */
  | { kind: "not_applied"; code: LedgerFailureCode | "refused" }
  /** The apply was sent and its settlement was not seen. */
  | { kind: "unknown"; operationId: string | null };

/** The preflight of `edits` on `baseline`. A stale baseline not renewed
 * before is renewed, and the check waits for the edits to be staged again
 * on the renewed declaration. */
async function preflight(
  port: ModeloPort,
  session: FormSession,
  baseline: ModeloEditApplyBaselineV1,
  language: OutputLanguage,
  renewedBefore: boolean,
  onRenewed: (baseline: ModeloEditApplyBaselineV1) => Promise<void>,
  onRebase: (report: ModeloFormRebaseEntryV1[]) => void,
  renewal: { claim(): boolean; release(): void },
): Promise<ReviewPhase> {
  try {
    const outcome = await port.edit(
      "modelo.edit.preflight",
      modeloEditBody(
        editSubmission(baseline, session.staged.values(), language, true),
      ),
    );
    if (outcome.kind !== "settled")
      return { kind: "check_failed", code: "refused" };
    const read = outcome.result;
    const answer = read.outcome;
    if (answer.outcome === "evaluated") {
      // What became of each held change, as a check of them says: a box that
      // moved under it marks it, and one that no longer takes it drops it.
      // A refused check says nothing about them.
      if (read.rebase.some((entry) => entry.outcome !== "kept"))
        onRebase(read.rebase);
      return {
        kind: "checked",
        findings: read.findings,
        operatorEntriesUnknown: read.operator_entries_unknown,
      };
    }
    if (answer.refusal.kind !== "stale_edit_baseline" || renewedBefore)
      return { kind: "refused", words: read.refusal_words };
  } catch (error) {
    return { kind: "check_failed", code: ledgerFailure(error).code };
  }
  // One renewal at a time: a check that finds the baseline stale while a
  // renewal is under way waits for the check that renewal starts.
  if (!renewal.claim()) return { kind: "checking" };
  try {
    const outcome = await port.submit("modelo.edit.renew", {
      baseline,
      output_language: language,
    });
    if (outcome.kind !== "settled")
      return { kind: "check_failed", code: "refused" };
    const next = outcome.result.renewed_baseline;
    if (!next) return { kind: "refused", words: outcome.result.refusal_words };
    await onRenewed(next);
    return { kind: "checking" };
  } catch (error) {
    return { kind: "check_failed", code: ledgerFailure(error).code };
  } finally {
    renewal.release();
  }
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
  onReread: () => Promise<void>;
  onPrerequisiteHeld?: (held: boolean) => void;
}) {
  const [phase, setPhase] = useState<ReviewPhase>({ kind: "checking" });
  const [renewed, setRenewed] = useState<ModeloEditApplyBaselineV1 | null>(
    null,
  );
  // An unknown apply holds every apply until the form is read again, also
  // across closing and reopening the dialog: a new read is a new envelope.
  const [held, setHeld] = useState<{
    operationId: string | null;
    read: ModeloWorkbenchFormProjectionV1;
  } | null>(null);
  const alive = useRef(true);
  const checks = useRef(0);
  // The declaration as read before the last renewal, until its report.
  const renewedFrom = useRef<ModeloWorkbenchFormProjectionV1 | null>(null);
  const renewing = useRef(false);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const admitted = envelope.admitted_baseline;
  // A baseline the form admitted after the renewal supersedes it.
  const baseline =
    renewed && (!admitted || renewed.issued_at >= admitted.issued_at)
      ? renewed
      : admitted;
  const unknown = held !== null && held.read === envelope;

  const check = useCallback(async () => {
    if (!baseline) {
      setPhase({ kind: "check_failed", code: "not_admitted" });
      return;
    }
    setPhase({ kind: "checking" });
    // Only the latest check speaks: a renewal starts another.
    const ticket = ++checks.current;
    const answer = await preflight(
      port,
      session,
      baseline,
      language,
      renewed !== null && baseline === renewed,
      async (next) => {
        // The declaration is read again; the renewed baseline then starts a
        // new check, whose report is applied to that read.
        renewedFrom.current = envelope;
        setRenewed(next);
        await onReread();
      },
      (report) => {
        session.rebase(report, renewedFrom.current);
        renewedFrom.current = null;
      },
      {
        claim: () => {
          if (renewing.current) return false;
          renewing.current = true;
          return true;
        },
        release: () => {
          renewing.current = false;
        },
      },
    );
    if (alive.current && ticket === checks.current) setPhase(answer);
  }, [baseline, port, session, language, renewed, onReread, envelope]);

  // Each opening checks the edits as they now stand; a re-read after an
  // unknown apply releases the hold.
  const latest = useRef(check);
  useEffect(() => {
    latest.current = check;
  });
  const editsKey = [...session.staged.keys()].join("\u0000");
  const baselineId = baseline?.baseline_id ?? null;
  useEffect(() => {
    // Nothing staged, as after an apply, has nothing to check.
    if (!open || unknown || editsKey === "") return;
    void latest.current();
  }, [open, unknown, editsKey, baselineId]);
  useEffect(() => {
    if (held && held.read !== envelope) setHeld(null);
  }, [held, envelope]);

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
    if (!baseline || unknown || phase.kind !== "checked") return;
    setPhase({ kind: "applying" });
    const run = await runOperation(
      port,
      () =>
        port.edit(
          "modelo.edit.apply",
          modeloEditBody(
            editSubmission(baseline, session.staged.values(), language),
          ),
        ),
      () => alive.current,
    );
    if (run.kind === "settled" || run.kind === "saved_unread") {
      session.discardAll();
      setRenewed(null);
      if (alive.current) setPhase({ kind: "applied" });
      await onReread();
    } else if (run.kind === "refused") {
      if (alive.current) setPhase({ kind: "not_applied", code: "refused" });
      await readPrerequisite(baseline, run.operationId);
    } else if (run.kind === "not_sent") {
      if (alive.current) setPhase({ kind: "not_applied", code: run.code });
    } else {
      setHeld({ operationId: run.operationId, read: envelope });
      if (alive.current)
        setPhase({ kind: "unknown", operationId: run.operationId });
    }
  }, [
    baseline,
    unknown,
    phase.kind,
    port,
    session,
    onReread,
    envelope,
    language,
    readPrerequisite,
  ]);

  return {
    phase: unknown
      ? ({ kind: "unknown", operationId: held.operationId } as const)
      : phase,
    apply,
    recheck: () => void check(),
    prerequisite:
      standing && prerequisite && heldField
        ? { field: heldField, words: prerequisite.held.words }
        : null,
  };
}
