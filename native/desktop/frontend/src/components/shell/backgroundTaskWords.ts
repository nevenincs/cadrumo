import type { JobFailure, RowJobState } from "../../shell/backgroundTasks";
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
