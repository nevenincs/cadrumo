import type {
  JobFailure,
  JobNotice,
  RowJobState,
} from "../../shell/backgroundTasks";
import type { LedgerFailureCode } from "../../shell/ledger";
import type {
  LedgerClassifyJobApplyRefusal,
  LedgerClassifyJobChangeResult,
} from "../../shell/ledgerClassificationJobContract";
import type { Translate } from "../../shell/strings";

/** The words of each cause a movement of a job failed for. */
export const FAILURE_WORDS: Record<JobFailure, string> = {
  model_unavailable: "desktop.background_tasks.cause.model_unavailable",
  consent_required: "desktop.background_tasks.cause.consent_required",
  consent_revoked: "desktop.background_tasks.cause.consent_revoked",
  consent_expired: "desktop.background_tasks.cause.consent_expired",
  lane_changed: "desktop.background_tasks.cause.lane_changed",
  lane_refused: "desktop.background_tasks.cause.lane_refused",
  invalid_response: "desktop.background_tasks.cause.invalid_response",
  timed_out: "desktop.background_tasks.cause.timed_out",
  movement_not_found: "desktop.background_tasks.cause.movement_not_found",
  unknown: "desktop.background_tasks.cause.unknown",
  failed: "desktop.background_tasks.cause.failed",
};

/** What a movement's row says of the job that holds it. */
export function rowJobWords(t: Translate, state: RowJobState): string {
  if (state.kind === "classifying")
    return t("desktop.background_tasks.row.classifying");
  if (state.kind === "proposed")
    return t("desktop.background_tasks.row.proposed");
  return t("desktop.background_tasks.row.failed", {
    cause: t(FAILURE_WORDS[state.cause]),
  });
}

/** The words of what each change to a job came to. */
const OUTCOME_WORDS: Record<LedgerClassifyJobChangeResult["outcome"], string> =
  {
    enqueued: "desktop.background_tasks.outcome.enqueued",
    cancelled: "desktop.background_tasks.outcome.cancelled",
    cancelling: "desktop.background_tasks.outcome.cancelling",
    retried: "desktop.background_tasks.outcome.retried",
    dismissed: "desktop.background_tasks.outcome.dismissed",
    authorised: "desktop.background_tasks.outcome.authorised",
    consent_revoked: "desktop.background_tasks.outcome.consent_revoked",
  };

const callFailure = (t: Translate, code: LedgerFailureCode) =>
  t(
    code === "unknown"
      ? "desktop.background_tasks.call_unknown"
      : "desktop.background_tasks.call_failed",
  );

/** What an action on a job, or an ask for a new one, came to, in words: a
 * refusal by the words and next step the backend served for it. */
export function jobNoticeText(t: Translate, notice: JobNotice): string {
  switch (notice.kind) {
    case "resuming":
      return t("desktop.background_tasks.resuming");
    case "waiting":
      return t("desktop.background_tasks.waiting");
    case "changed":
      return t(OUTCOME_WORDS[notice.outcome]);
    case "applied":
      return t("desktop.background_tasks.outcome.applied", {
        applied: notice.applied,
        refused: notice.refused,
      });
    case "refused":
      return [
        notice.words ?? t("desktop.background_tasks.refused"),
        notice.step?.words,
      ]
        .filter((part, at, parts) => part && parts.indexOf(part) === at)
        .join(" ");
    case "failed":
      return callFailure(t, notice.code);
  }
}

/** The words of each cause an accepted proposal was not applied for, with
 * the step that follows. */
export const APPLY_REFUSAL_WORDS: Record<
  LedgerClassifyJobApplyRefusal,
  string
> = {
  stale: "desktop.background_tasks.apply_refusal.stale",
  not_proposed: "desktop.background_tasks.apply_refusal.not_proposed",
  not_in_job: "desktop.background_tasks.apply_refusal.not_in_job",
  movement_not_found:
    "desktop.background_tasks.apply_refusal.movement_not_found",
  business_pct_required:
    "desktop.background_tasks.apply_refusal.business_pct_required",
  business_pct_not_applicable:
    "desktop.background_tasks.apply_refusal.business_pct_not_applicable",
  category_unavailable:
    "desktop.background_tasks.apply_refusal.category_unavailable",
  rejected: "desktop.background_tasks.apply_refusal.rejected",
};
