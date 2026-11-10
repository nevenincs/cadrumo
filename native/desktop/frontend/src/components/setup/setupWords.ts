import type {
  GoogleAccount,
  SetupBlockedReason,
  SetupFailureCategory,
  SetupItemId,
  SetupItemKind,
  SetupOutcome,
  SetupRecovery,
  SetupRetry,
  SetupRow,
  SetupStaleReason,
  SetupState,
  SetupStep,
} from "../../ipc/componentSetup";
import type { Translate } from "../../shell/strings";

// The window's words for setup and the Google account. The host sends codes
// only, and every one is worded here from the setup strings: an item's name,
// the one sentence that states a row's state and its button, a
// failure, a retry notice and a plan part, and what the shell itself says of
// a step, an outcome, a refusal and the Google account.
// A row's sentence is the one place its state is said. No closed value is
// ever shown as it is.
//
// Every key is written whole, in a table keyed by the closed value's type, so
// the compiler requires a key for each member and the shell's key check sees
// each one. A value the host sends that the table lacks is a newer host's:
// it is said by the general sentence beside its table, never as a raw key.

/** One catalogue key, written whole. */
type Key = string;

/** The words for `value`, or those for the general case when the table does
 * not hold it. The own-property test keeps an inherited name such as
 * `constructor` from reading as a member. */
function wordsFor<Member extends string>(
  t: Translate,
  table: Readonly<Record<Member, Key>>,
  value: string,
  general: Key,
): string {
  return t(Object.hasOwn(table, value) ? table[value as Member] : general);
}

const ITEM_NAME: Readonly<Record<SetupItemKind, Key>> = {
  browser: "desktop.setup.item.browser",
  local_ai: "desktop.setup.item.local_ai",
};

const STATE_SENTENCE: Readonly<Record<SetupState, Key>> = {
  absent: "desktop.setup.state.absent",
  provisioning: "desktop.setup.state.provisioning",
  verifying: "desktop.setup.state.verifying",
  ready: "desktop.setup.state.ready",
  stale: "desktop.setup.state.stale",
  failed: "desktop.setup.state.failed",
  blocked: "desktop.setup.state.blocked",
  unknown: "desktop.setup.state.unknown",
};

const STALE_SENTENCE: Readonly<Record<SetupStaleReason, Key>> = {
  older_revision: "desktop.setup.stale.older_revision",
  program_too_old: "desktop.setup.stale.program_too_old",
};

const BLOCKED_SENTENCE: Readonly<Record<SetupBlockedReason, Key>> = {
  offline: "desktop.setup.blocked.offline",
  needs_person: "desktop.setup.blocked.needs_person",
  hardware: "desktop.setup.blocked.hardware",
  not_in_this_build: "desktop.setup.blocked.not_in_this_build",
};

const ACTION_WORDS: Readonly<Record<SetupRecovery, Key>> = {
  set_up: "desktop.setup.action.set_up",
  update: "desktop.setup.action.update",
  try_again: "desktop.setup.action.try_again",
  resume: "desktop.setup.action.resume",
  check_again: "desktop.setup.action.check_again",
};

const FAILURE_SENTENCE: Readonly<Record<SetupFailureCategory, Key>> = {
  offline: "desktop.setup.failure.offline",
  host_unreachable: "desktop.setup.failure.host_unreachable",
  server_error: "desktop.setup.failure.server_error",
  secure_connection_failed: "desktop.setup.failure.secure_connection_failed",
  blocked_by_network: "desktop.setup.failure.blocked_by_network",
  disk_full: "desktop.setup.failure.disk_full",
  no_permission: "desktop.setup.failure.no_permission",
  damaged_download: "desktop.setup.failure.damaged_download",
  not_enough_memory: "desktop.setup.failure.not_enough_memory",
  memory_busy: "desktop.setup.failure.memory_busy",
  program_missing: "desktop.setup.failure.program_missing",
  program_not_running: "desktop.setup.failure.program_not_running",
  engine_program_unusable: "desktop.setup.failure.engine_program_unusable",
  interrupted: "desktop.setup.failure.interrupted",
  needs_sign_in: "desktop.setup.failure.needs_sign_in",
  not_in_this_build: "desktop.setup.failure.not_in_this_build",
  cancelled: "desktop.setup.failure.cancelled",
  unexpected: "desktop.setup.failure.unexpected",
};

/** An item's plain name, such as "Local AI", keyed by the row's item. An
 * item this window does not know is named by the setup's own title. */
export function itemName(t: Translate, item: SetupItemId): string {
  return wordsFor(t, ITEM_NAME, item, "desktop.setup.title");
}

/** A row's download size as the engine states it: unknown until the
 * download starts, nothing at all when its files are already here, else
 * the size. */
export function rowSizeWords(
  t: Translate,
  bytes: number | null,
  format: (bytes: number) => string,
): string {
  if (bytes === null) return t("desktop.setup.size_unknown");
  return bytes === 0 ? t("desktop.setup.plan_nothing") : format(bytes);
}

/** The one sentence stating a row's state and its reason. A reason this
 * window does not know leaves the state's own sentence, and a state it does
 * not know says the state is unknown. */
export function rowSentence(t: Translate, row: SetupRow): string {
  if (row.state === "stale" && row.stale_reason)
    return wordsFor(t, STALE_SENTENCE, row.stale_reason, STATE_SENTENCE.stale);
  if (row.state === "blocked" && row.blocked_reason)
    return wordsFor(
      t,
      BLOCKED_SENTENCE,
      row.blocked_reason,
      STATE_SENTENCE.blocked,
    );
  if (row.state === "failed" && row.failure)
    return failureWords(t, row.failure);
  return wordsFor(t, STATE_SENTENCE, row.state, STATE_SENTENCE.unknown);
}

/** The words of a row's one button; null when it offers none, which is also
 * what a button this window has no words for gets. */
export function actionWords(
  t: Translate,
  recovery: SetupRecovery | null,
): string | null {
  return recovery !== null && Object.hasOwn(ACTION_WORDS, recovery)
    ? t(ACTION_WORDS[recovery])
    : null;
}

/** The one sentence a failure is told by; a failure this window does not
 * know is told as an unexpected one. */
export function failureWords(
  t: Translate,
  failure: SetupFailureCategory,
): string {
  return wordsFor(t, FAILURE_SENTENCE, failure, FAILURE_SENTENCE.unexpected);
}

/** The notice shown before a retry's wait. */
export function retryWords(t: Translate, retry: SetupRetry): string {
  return t("desktop.setup.retry", {
    attempt: retry.attempt,
    seconds: retry.delay_s,
  });
}

/** One part of the local AI's plan: its program, or the one model being downloaded. */
export function partName(t: Translate, part: string): string {
  return part === "program"
    ? t("desktop.setup.part_program")
    : t("desktop.setup.part_download");
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

/** What a setup is doing while it works out its plan, before it asks for an
 * answer. Until the engine reports its first step the host is still
 * checking the request, such as a model with the agent service, which can
 * take long; that step is the plan itself, worded as such. */
export function planningWords(t: Translate, step: SetupStep | null): string {
  return step === null
    ? t("desktop.setup.step_checking")
    : t("desktop.setup.planning");
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

/** What a settled setup came to. */
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
    case "browser_not_removed":
      return t("desktop.setup.refused_browser_not_removed");
    case "local_ai_not_removed":
      return t("desktop.setup.refused_local_ai_not_removed");
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
