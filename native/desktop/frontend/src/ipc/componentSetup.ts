// Component setup (`desktop_setup_*`): the rows, plans, runs and refusals the
// host reports while it installs what the desktop needs. Field names and
// casing follow the host's serde output exactly.

// ---------------------------------------------------------------------------
// Component setup (desktop_setup_*)
// ---------------------------------------------------------------------------
//
// The software Cadrumo needs on this computer -- the browser and the local AI
// (its program and every model it runs, as one item) -- read and set up by
// the window's own component engine. The profile's Google account travels in
// the same snapshot, but it is not setup: it is the profile's own sign-in,
// read and changed on its own through the held person session. The host
// pushes a fresh `DesktopSetup` on the observe channel whenever the engine or
// a Google act changes it; nothing polls. The snapshot carries codes and
// locale-neutral facts only. The window words every item name, state,
// failure, action, note, retry notice and plan part from its own
// setup strings (`components/setup/setupWords.ts`). Never render a closed
// value itself.

/** `browser` or `local_ai`. */
export type SetupItemId = string;

export type SetupItemKind = "browser" | "local_ai";

export type SetupState =
  | "absent"
  | "provisioning"
  | "verifying"
  | "ready"
  | "stale"
  | "failed"
  | "blocked"
  | "unknown";

export type SetupBlockedReason =
  "offline" | "needs_person" | "hardware" | "not_in_this_build";

export type SetupStaleReason = "older_revision" | "program_too_old";

export type SetupFailureCategory =
  | "offline"
  | "host_unreachable"
  | "secure_connection_failed"
  | "blocked_by_network"
  | "disk_full"
  | "no_permission"
  | "damaged_download"
  | "not_enough_memory"
  | "memory_busy"
  | "program_missing"
  | "program_not_running"
  | "interrupted"
  | "needs_sign_in"
  | "not_in_this_build"
  | "cancelled"
  | "unexpected";

/** The one button a row offers, worded by the window. */
export type SetupRecovery =
  "set_up" | "update" | "try_again" | "resume" | "check_again";

export type SetupCheckMode = "quick" | "full";

export type SetupStep =
  "plan" | "preflight" | "download" | "install" | "verify" | "cleanup";

/** One item's derived state, with exactly the reason it needs. */
export type SetupRow = {
  item: SetupItemId;
  kind: SetupItemKind;
  /** Which check produced the row. */
  mode: SetupCheckMode;
  state: SetupState;
  stale_reason: SetupStaleReason | null;
  blocked_reason: SetupBlockedReason | null;
  failure: SetupFailureCategory | null;
  recovery: SetupRecovery | null;
  /** The operator action that offers `recovery`, such as
   * `operator.provision.browser`; null exactly when `recovery` is. An
   * identifier for routing, never shown. */
  recovery_action_id: string | null;
  version: string | null;
  size_bytes: number | null;
};

/** A status read or a full check this window started. A settled check has
 * already replaced `rows`; a failed one leaves the earlier rows, except a
 * status read refused because the local engine record cannot be read, which
 * replaces them with the browser row alone. */
export type SetupCheck = {
  operation_id: string;
  kind: "status_quick" | "status_full" | "verify";
  stage: "running" | "done" | "failed";
  /** The category a failed check carried, worded as a row's failure is; null
   * while it runs, when it is done, and when a failure carried no category. */
  failure: SetupFailureCategory | null;
  /** Why the check was refused before the engine ran: the person's selection
   * of local models could not be handed to it, or the local engine record
   * cannot be read, when a status read still reads the browser alone. Only on
   * a failed check, and never with a `failure`. Worded as a command's refusal
   * is. */
  refusal: SetupRefusalCode | null;
};

/** One model explicitly requested for download, independently of task configuration. */
export type SetupModelDownload = { lane: string; model: string };

/** A local AI plan part: the program, a configured task, or an explicit download.
 * A part sharing an earlier part's download has size 0. */
export type SetupPlanPart = {
  part: string;
  /** The exact model in an explicit download plan. */
  model?: string | null;
  /** Null when the size is not known before the download starts. */
  download_bytes: number | null;
  /** The folder this part is stored in. */
  destination: string | null;
};

/** One entry of the plan a person approves: what, how large, from where and
 * where it is stored. Shown, never sent back. */
export type SetupPlanEntry = {
  item: SetupItemId;
  /** Null when the size is not known before the download starts. */
  download_bytes: number | null;
  source_hosts: string[];
  /** The folder the entry as a whole goes into; null where only an outside
   * program installs, and for the local AI, whose parts each name theirs. */
  destination: string | null;
  installs_outside_program: boolean;
  /** Another entry of this plan that downloads the same files. */
  shares_download_with: SetupItemId | null;
  /** The local AI's parts in the order setup carries them out; empty for
   * any other item. */
  parts: SetupPlanPart[];
};

/** The plan awaiting approval. `plan_digest` is what an answer binds. */
export type SetupReview = {
  plan_digest: string;
  entries: SetupPlanEntry[];
  known_download_bytes: number;
  has_unknown_size: boolean;
  installs_outside_program: boolean;
  required_bytes: number;
  /** Null when the free space could not be read. */
  free_bytes: number | null;
  space_sufficient: boolean;
};

export type SetupRetry = {
  attempt: number;
  delay_s: number;
};

export type SetupItemResult = {
  changed: boolean;
  /** Null when the item ended usable. */
  failure: SetupFailureCategory | null;
  transferred_bytes: number;
};

/** One part of the local AI's setup: its program, or the model one part
 * pulls. A part whose model an earlier part pulls moves no bytes of its own. */
export type SetupPartProgress = {
  part: string;
  /** The model the part pulls, always present for a model part so that
   * model's row finds its progress; absent for the program (`part` is
   * "program"). */
  model?: string;
  step: SetupStep | null;
  /** Both null until the part's bytes move or while its size is unknown. */
  completed: number | null;
  total: number | null;
  result: SetupItemResult | null;
};

/** The item a setup sets up while it runs: its current step, byte progress
 * and last retry notice, then its result once setup settles. */
export type SetupItemProgress = {
  item: SetupItemId;
  step: SetupStep | null;
  /** Both null while the size is unknown: show an indeterminate bar. */
  completed: number | null;
  total: number | null;
  retry: SetupRetry | null;
  result: SetupItemResult | null;
  /** The local AI's parts in the order setup carries them out; empty for any
   * other item. */
  parts: SetupPartProgress[];
};

export type SetupOutcome =
  | "completed"
  | "nothing_to_do"
  | "rejected"
  | "plan_changed"
  | "not_enough_space"
  | "interrupted"
  | "cancelled"
  /** The setup did not finish; see `failure`. */
  | "failed";

/** One item's setup this window started or joined. */
export type SetupRun = {
  /** The one item this setup sets up. */
  item: SetupItemId;
  operation_id: string;
  stage: "planning" | "review" | "running" | "settled";
  /** Present exactly while `stage` is "review". */
  review: SetupReview | null;
  /** The run's item alone, once setup knows it. */
  items: SetupItemProgress[];
  /** Whether Cancel can be offered now. */
  cancellable: boolean;
  cancel_requested: boolean;
  /** Present exactly once `stage` is "settled". */
  outcome: SetupOutcome | null;
  /** Present exactly when `outcome` is "failed". */
  failure: SetupFailureCategory | null;
};

/** The profile's stored Google sign-in, as the product reads it. */
export type GoogleAccountState =
  "signed_in" | "signed_out" | "not_in_this_build" | "unknown";

/** The sign-in or sign-out this window started. */
export type GoogleActStage = "idle" | "signing_in" | "signing_out" | "failed";

/** The signed-in profile's Google account: not a setup item. */
export type GoogleAccount = {
  /** Null until the stored sign-in has been read. */
  state: GoogleAccountState | null;
  /** The account's address; present only when signed in. */
  email: string | null;
  /** The profile's saved folder, present only with a stored Drive grant. */
  drive_folder_id: string | null;
  stage: GoogleActStage;
  /** Present exactly when `stage` is "failed". */
  failure: SetupFailureCategory | null;
};

export type SetupSnapshot = {
  /** Empty until the first status read settles. */
  rows: SetupRow[];
  /** Null until the first status read settles, as are the next two. */
  rows_mode: SetupCheckMode | null;
  /** Every item ready or usable: Cadrumo is set up. */
  complete: boolean | null;
  /** Setup cannot complete on this computer's hardware. */
  hardware_limited: boolean | null;
  check: SetupCheck | null;
  /** Each item's setup, at most one per item, in the rows' item order. Items
   * set up independently and at the same time. */
  runs: SetupRun[];
  google: GoogleAccount;
  /** The redacted report "Copy details" puts on the clipboard. */
  details: string;
};

/** What the observe channel carries and every setup command answers.
 * `revision` grows with every change; `snapshot` is present exactly when
 * `state` is "ready". */
export type DesktopSetup = {
  revision: number;
  /** `ready` with the snapshot whether or not anyone is signed in and
   * whether or not the profile's runtime answers: the components are this
   * installation's. Signed out, `google` reads `signed_out` and what is a
   * profile's is refused as `not_signed_in`; signed in while the runtime
   * does not answer, `google` reads `unknown` and what is the profile's is
   * refused as `unavailable`. `unavailable` only while this window's own
   * setup engine cannot be read. */
  state: "unavailable" | "ready";
  snapshot: SetupSnapshot | null;
};

/** Why a setup command was refused; a host failure rejects as `HostFailure`. */
export type SetupRefusalCode =
  /** No profile is signed in, for what is a profile's: its Google account,
   * or a model of its person's local model list. */
  | "not_signed_in"
  /** Another setup, started elsewhere, is running. */
  | "busy"
  /** The plan changed since it was shown; show the new one. */
  | "plan_changed"
  /** No plan of that setup is awaiting an answer, or it is not this window's. */
  | "not_pending"
  /** The setup cannot be cancelled now. */
  | "not_cancellable"
  /** The runtime or the profile's session could not carry the request. */
  | "unavailable"
  /** The requested model cannot be handed to the engine: it is not on a
   * turned-on local lane's model list, or its name is not one the engine
   * can pull. */
  | "model_selection_unusable"
  /** The engine did not remove the model. */
  | "model_not_removed"
  /** The engine did not remove the browser. */
  | "browser_not_removed"
  /** The engine did not remove the local AI, or its program. */
  | "local_ai_not_removed";

/** What a removal deletes from this computer: the browser, the local AI with
 * the models on the person's lists, or the local AI's program alone. */
export type SetupRemoval = "browser" | "local_ai" | "local_ai_program";

export type SetupRefusal = { code: SetupRefusalCode };
