import type {
  GoogleAccount,
  SetupFailureCategory,
  SetupItemId,
  SetupItemKind,
  SetupNote,
  SetupOutcome,
  SetupRecovery,
  SetupRetry,
  SetupRow,
  SetupRun,
  SetupStep,
} from "../../ipc/contract";
import type { Translate } from "../../shell/strings";

// The window's words for setup and the Google account. The host sends codes
// only, and every one is worded here from the setup strings: an item's name,
// the one sentence that states a row's state, its note and its button, a
// failure, a retry notice and a plan part, and what the shell itself says of
// a step, an outcome, a refusal and the Google account.
// A row's sentence is the one place its state is said. No closed value is
// ever shown as it is.

/** An item's plain name, such as "Local AI"; an item's id is its kind. */
export function itemName(
  t: Translate,
  item: SetupItemKind | SetupItemId,
): string {
  return t(`desktop.setup.item.${item}`);
}

/** The one sentence stating a row's state and its reason. */
export function rowSentence(t: Translate, row: SetupRow): string {
  if (row.state === "stale" && row.stale_reason)
    return t(`desktop.setup.stale.${row.stale_reason}`);
  if (row.state === "blocked" && row.blocked_reason)
    return t(`desktop.setup.blocked.${row.blocked_reason}`);
  if (row.state === "failed" && row.failure)
    return failureWords(t, row.failure);
  return t(`desktop.setup.state.${row.state}`);
}

/** A usable item's secondary fact, such as "Downloaded, not loaded yet." */
export function noteWords(t: Translate, note: SetupNote): string {
  return t(`desktop.setup.note.${note}`);
}

/** The words of a row's one button; null when it offers none. */
export function actionWords(
  t: Translate,
  recovery: SetupRecovery | null,
): string | null {
  return recovery === null ? null : t(`desktop.setup.action.${recovery}`);
}

/** The one sentence a failure is told by. */
export function failureWords(
  t: Translate,
  failure: SetupFailureCategory,
): string {
  return t(`desktop.setup.failure.${failure}`);
}

/** The notice shown before a retry's wait. */
export function retryWords(t: Translate, retry: SetupRetry): string {
  return t("desktop.setup.retry", {
    attempt: retry.attempt,
    seconds: retry.delay_s,
  });
}

/** One part of the local AI's plan: its program, or the model selected for one role. */
export function partName(t: Translate, part: string): string {
  return part === "program"
    ? t("desktop.setup.part_program")
    : t("desktop.setup.part_model", { role: t(`desktop.setup.role.${part}`) });
}

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
  failure: SetupFailureCategory | null,
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
      return failure
        ? failureWords(t, failure)
        : t("desktop.setup.outcome_failed");
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
    case "model_selection_unusable":
      return t("desktop.setup.refused_model_selection_unusable");
    case "model_size_unstated":
      return t("desktop.setup.refused_model_size_unstated");
    default:
      return t("desktop.setup.refused_other");
  }
}

/** The Google account's one line: what is happening now, else how the
 * profile's sign-in reads. A failed act says its failure instead. */
export function googleWords(t: Translate, google: GoogleAccount): string {
  if (google.stage === "signing_in") return t("desktop.google.waiting");
  if (google.stage === "signing_out") return t("desktop.google.signing_out");
  if (google.stage === "failed" && google.failure)
    return failureWords(t, google.failure);
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
