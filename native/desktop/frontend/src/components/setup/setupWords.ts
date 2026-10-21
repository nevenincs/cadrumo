import type {
  GoogleAccount,
  SetupOutcome,
  SetupRow,
  SetupRun,
  SetupStep,
} from "../../ipc/contract";
import type { Translate } from "../../shell/strings";

// The window's own words for setup and the Google account. Each item's name,
// state sentence, note and button come from the host already in the
// profile's language, and the sentence is the one place a row's state is
// said; what is worded here is only what the shell itself says: a step, an
// outcome, a refusal and the Google account's line. No closed value is ever
// shown as it is.

/** How a row's state is marked beside its sentence, which says it in words. */
export type RowTone = "ready" | "working" | "attention";

export function rowTone(row: SetupRow): RowTone {
  switch (row.state) {
    case "ready":
    case "stale":
      return "ready";
    case "provisioning":
    case "verifying":
      return "working";
    default:
      return "attention";
  }
}

export function stepWords(t: Translate, step: SetupStep | null): string {
  switch (step) {
    case "plan":
    case null:
      return t("desktop.setup.step_waiting");
    case "preflight":
      return t("desktop.setup.step_connecting");
    case "download":
      return t("desktop.setup.step_downloading");
    case "install":
      return t("desktop.setup.step_installing");
    case "verify":
      return t("desktop.setup.step_checking");
    case "cleanup":
      return t("desktop.setup.step_tidying");
  }
}

/** How far a setup has come over every item it planned, from 0 to 1: a
 * finished item counts whole, the running one by its bytes where known. */
export function overallShare(run: SetupRun): number {
  if (run.items.length === 0) return 0;
  const done = run.items.reduce((sum, item) => {
    if (item.result) return sum + 1;
    if (item.completed !== null && item.total !== null && item.total > 0)
      return sum + item.completed / item.total;
    return sum;
  }, 0);
  return Math.min(1, done / run.items.length);
}

/** What a settled setup came to, said once in the dialog. */
export function outcomeWords(
  t: Translate,
  outcome: SetupOutcome,
  failureSentence: string | null,
): string {
  switch (outcome) {
    case "completed":
      return t("desktop.setup.outcome_completed");
    case "nothing_to_do":
      return t("desktop.setup.outcome_nothing_to_do");
    case "rejected":
      return t("desktop.setup.outcome_rejected");
    case "plan_changed":
      return t("desktop.setup.outcome_plan_changed");
    case "not_enough_space":
      return t("desktop.setup.outcome_not_enough_space");
    case "interrupted":
      return t("desktop.setup.outcome_interrupted");
    case "cancelled":
      return t("desktop.setup.outcome_cancelled");
    case "failed":
      return failureSentence ?? t("desktop.setup.outcome_failed");
  }
}

/** The one-line toast a settled setup leaves behind, or null for an answer
 * that needs no telling: a plan the person turned down themselves. */
export function outcomeToast(
  t: Translate,
  outcome: SetupOutcome,
): string | null {
  switch (outcome) {
    case "completed":
    case "nothing_to_do":
      return t("desktop.setup.toast_done");
    case "rejected":
      return null;
    case "cancelled":
      return t("desktop.setup.toast_cancelled");
    case "plan_changed":
    case "not_enough_space":
    case "interrupted":
    case "failed":
      return t("desktop.setup.toast_not_finished");
  }
}

/** Why a setup command was refused, in words; an unknown code, or a host
 * that failed to carry the command, gets the general sentence. */
export function refusalWords(t: Translate, code: string): string {
  switch (code) {
    case "not_signed_in":
      return t("desktop.setup.refused_not_signed_in");
    case "busy":
      return t("desktop.setup.refused_busy");
    case "plan_changed":
      return t("desktop.setup.refused_plan_changed");
    case "not_pending":
      return t("desktop.setup.refused_not_pending");
    case "not_cancellable":
      return t("desktop.setup.refused_not_cancellable");
    case "unavailable":
      return t("desktop.setup.refused_unavailable");
    default:
      return t("desktop.setup.refused_other");
  }
}

/** The Google account's one line: what is happening now, else how the
 * profile's sign-in reads. A failed act says its own sentence instead. */
export function googleWords(t: Translate, google: GoogleAccount): string {
  if (google.stage === "signing_in") return t("desktop.google.waiting");
  if (google.stage === "signing_out") return t("desktop.google.signing_out");
  if (google.stage === "failed" && google.sentence) return google.sentence;
  switch (google.state) {
    case null:
      return t("desktop.google.checking");
    case "signed_in":
      return google.email
        ? t("desktop.google.signed_in", { email: google.email })
        : t("desktop.google.signed_in_plain");
    case "signed_out":
      return t("desktop.google.signed_out");
    case "not_in_this_build":
      return t("desktop.google.not_in_this_build");
    case "unknown":
      return t("desktop.google.unknown");
  }
}

/** Whether the Google account can be signed into from here now. */
export function canSignInGoogle(google: GoogleAccount | null): boolean {
  return (
    google !== null &&
    google.stage !== "signing_in" &&
    google.stage !== "signing_out" &&
    google.state !== null &&
    google.state !== "signed_in" &&
    google.state !== "not_in_this_build"
  );
}
