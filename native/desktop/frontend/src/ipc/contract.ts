// The desktop shell's published IPC contract: the app commands the Rust host
// registers, with the arguments and results each carries. The frames its
// channels carry and the postMessage bridge between the shell document and
// the documentation frame are declared beside it, in this directory.
//
// Types only; nothing here runs. Field names and casing follow the host's
// serde output exactly.

import type { Channel } from "@tauri-apps/api/core";
import type { AgentAccessAnswer } from "../shell/agentAccess";
import type {
  AgentAnswerResult,
  AgentApproval,
  AgentAttachmentCard,
  AgentAttachmentGrants,
  AgentAttachmentPolicy,
  AgentAttachmentRefusal,
  AgentAttachmentRelease,
  AgentAttachmentScope,
  AgentCatalogAnswer,
  AgentDropSignal,
  AgentModelLicence,
  AgentQuestionnaire,
  AgentQuestionnaireAnswer,
  AgentSendRequest,
  AgentSendResult,
  AgentServiceStatus,
  AgentStreamEvent,
  AgentUploadEvent,
  AgentUploadPick,
} from "../shell/agentSession";
import type {
  AgentConversationRecord,
  AgentDocumentPage,
  AgentDocumentsQuery,
  AgentSnapshot,
  AgentTurnRecord,
} from "../shell/agentViews";
import type {
  ProviderSettingsAnswer,
  ProviderSettingsRecord,
  ProviderSignInSnapshot,
} from "../shell/providerSettings";
import type {
  ManagerSignal,
  ManagerStatus,
  PasswordChangeResult,
  ProfileDeleteReview,
  ProfileList,
  SignInSignal,
  SignInStatus,
  SignOutResult,
} from "./account";
import type {
  DesktopSetup,
  SetupCheckMode,
  SetupItemId,
  SetupModelDownload,
  SetupRemoval,
} from "./componentSetup";
import type { DiagnosticsSnapshot } from "./diagnostics";
import type {
  AboutInfo,
  DesktopEnvironment,
  DesktopLanguage,
} from "./environment";
import type {
  SedeClipboardAction,
  SedeViewDelivery,
  SedeViewInput,
  SedeViewVerb,
} from "./sedeViewMessages";
import type {
  TerminalAck,
  TerminalClose,
  TerminalClosed,
  TerminalKind,
  TerminalOpened,
  TerminalResize,
  TerminalSize,
} from "./terminalFrames";

// ---------------------------------------------------------------------------
// Launch token
// ---------------------------------------------------------------------------

declare const shellTokenBrand: unique symbol;

/**
 * The per-launch secret every app command requires: 32 random bytes as 64
 * lowercase hex characters.
 *
 * The host injects it into the shell document only, when that document is the
 * top frame on a shell origin, as `window.__CADRUMO_SHELL__.token`. The getter
 * returns it once and deletes itself, so read it once at startup and keep it
 * in module scope. Never post it to the documentation frame, never put it in a
 * URL, storage or a log, and never place it in a bridge envelope.
 */
export type ShellToken = string & { readonly [shellTokenBrand]: true };

/** The object the host's initialization script defines on the shell window. */
export interface ShellGlobal {
  /** Present until its first read; `undefined` afterwards. */
  readonly token?: string;
}

declare global {
  interface Window {
    /** Absent in a browser preview and in every frame but the shell's top frame. */
    readonly __CADRUMO_SHELL__?: ShellGlobal;
  }
}

/**
 * Every app command takes the token. A JSON object call carries it as the
 * `token` argument; a call with a raw body (or the JSON byte array Tauri sends
 * once it falls back to postMessage) carries it in the `x-cadrumo-token`
 * header instead. A missing or wrong token is refused with
 * `invalid_arguments` before the command runs.
 */
export type Authorized<Arguments extends object = Record<never, never>> =
  Arguments & { token: ShellToken };

/** Header names for commands whose body is raw bytes. */
export type TokenHeader = "x-cadrumo-token";

/** The header naming the session a raw-body `terminal_write` addresses. */
export type SessionHeader = "x-cadrumo-session";

// ---------------------------------------------------------------------------
// Failures
// ---------------------------------------------------------------------------

/** `ErrorCode` in `native/application/src/error/application.rs`. */
export type HostErrorCode =
  | "invalid_arguments"
  | "package_unavailable"
  | "environment_failed"
  | "timed_out"
  | "output_limit"
  | "spawn_failed"
  | "child_failed"
  | "read_failed"
  | "write_failed"
  | "resize_failed"
  | "cleanup_failed"
  | "session_unavailable"
  | "setup_failed"
  | "queue_full"
  | "cli_busy"
  | "cli_wait_timed_out"
  | "lock_poisoned"
  | "log_unavailable"
  | "desktop_unavailable"
  | "webview_failed"
  | "webview_process_failed"
  | "webview_monitor_unavailable"
  | "unsupported_platform"
  | "instance_lock_foreign"
  | "manager_unavailable"
  | "manager_dispatch_failed"
  | "installation_unavailable"
  | "installation_refused"
  | "installation_cancelled"
  | "installation_failed"
  | "installation_unsettled"
  | "panic";

/** `Operation` in `native/application/src/error/application.rs`. */
export type HostOperation =
  | "launch"
  | "package"
  | "environment"
  | "cli"
  | "terminal"
  | "logging"
  | "webview"
  | "shutdown"
  | "manager"
  | "installation";

/**
 * The serialized `ApplicationError`: the value a refused command rejects
 * with. `message` is a fixed English sentence per code; the shell shows its
 * own localized text keyed on `code`.
 */
export type HostFailure = {
  code: HostErrorCode;
  operation: HostOperation;
  message: string;
  /** Safe OS classification; original error text and paths stay native. */
  ioKind?: string;
  osCode?: number;
};

/** `ProcessRole` in `native/application/src/process/status.rs`. */
export type ProcessRole =
  | "environment"
  | "cli"
  | "tui"
  | "repl"
  | "console"
  | "sign_in"
  | "manager_dispatch";

// ---------------------------------------------------------------------------
// Logs (logs_subscribe, logs_unsubscribe)
// ---------------------------------------------------------------------------

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

/** Open enumeration: render unknown sources. */
export type LogSource = "python" | "host" | "manager" | (string & {});

/** Roles are open: Python workers and agents also write records. */
export type LogProcess = { role: string; pid: number };

export type LogContext = Record<string, string | number | boolean | null>;

export type LogRecord = {
  /** Increases by one per record across the host's ring. */
  seq: number;
  source: LogSource;
  /** The timestamp as written; empty when the line carried none. */
  timestamp: string;
  /**
   * Unix milliseconds in UTC when the record names an instant. Null for
   * legacy Python timestamps written without a timezone and unmatched lines.
   */
  timestampMs: number | null;
  level: LogLevel | null;
  logger: string | null;
  message: string;
  /** Continuation lines, such as a traceback. */
  detail: string | null;
  /** The writer or child process the event concerns, when known. */
  process: LogProcess | null;
  /** Bounded, scrubbed scalar diagnostic fields, including correlation. */
  context: LogContext;
};

export type LogSourceKind = "available" | "missing" | "unreadable";

/** "missing" and "unreadable" are distinct from an empty list of records. */
export type LogSourceState = {
  kind: LogSourceKind;
  /** The log file the state describes. */
  detail: string;
  /** Why the file could not be read; set only for `unreadable`. */
  failure: HostFailure | null;
  /** Complete file rows rejected by the admitted schema since polling resumed. */
  rejected: number;
};

/**
 * Independent file availability; host events are read from memory. A
 * `manager` state appears once a standalone manager writes its log: a desktop
 * that hosts supervision itself reports it among the host events.
 */
export type LogSourceStates = {
  [source: string]: LogSourceState;
  python: LogSourceState;
};

/**
 * One delivery on a subscription's channel; at most ten per second. A new
 * subscription starts from up to 5,000 records of backlog in a 10,000-record
 * ring. Each batch holds at most 5,000 records and about 1 MiB of serialized
 * records, so a large backlog arrives over several batches, in `seq` order.
 */
export type LogBatch = {
  records: LogRecord[];
  /** Records this subscription lost to ring overflow since its previous batch. */
  dropped: number;
  states: LogSourceStates;
};

export type LogSubscription = {
  subscription: number;
  states: LogSourceStates;
};

// ---------------------------------------------------------------------------
// Shell services
// ---------------------------------------------------------------------------

/**
 * Plain clipboard text. A write is refused with `invalid_arguments` when
 * `text` exceeds 1 MiB (1,048,576 bytes) in UTF-8, which is not the same
 * bound as `text.length`.
 */
export type ClipboardText = { text: string };

export type TerminalOpenArguments = TerminalSize & {
  kind: TerminalKind;
  /** Receives the session's frames, each as an `ArrayBuffer`. */
  frames: Channel<ArrayBuffer>;
};

export type StartupPhase = "environment" | "runtime" | "workspace";

export type StartupProgress = {
  phase: StartupPhase;
  locale: string | null;
  failure: HostFailure | null;
};

/** One model the person added by name to a local lane's model list. */
export type AgentListedModel = { lane: string; model: string };
/** Where the model documents are read with comes from, as the service serves it. */
export type AgentReadingSource = "chosen" | "default" | "none";

/**
 * The models the person added to the local lanes' lists, in the order added,
 * and the model documents are read with, the one the person selected in the
 * agent's model picker on any lane, with the revision a change sends back; or
 * a stored record nobody can read, which lists and selects no model and
 * carries its reset guard. A lane's recommended models are its catalogue's
 * and are not listed here. `local_lanes` are the catalogue's lanes on this
 * computer, whose models the picker offers from their lists.
 */
export type AgentLocalModels =
  | {
      state: "readable";
      models: AgentListedModel[];
      /** The model documents are read with now, as the service decides it. */
      reading: AgentListedModel | null;
      /** Where `reading` comes from: the person's stored choice, the
       * installed default that stands in for none, or none at all. */
      reading_source: AgentReadingSource;
      local_lanes: string[];
      revision: string;
    }
  | { state: "unreadable"; local_lanes: string[]; revision: string };

/** The engine that serves the local models, as the service names it. */
export type AgentLocalEngineToken = "llamacpp" | "ollama";
/** Where the local models run: the device the engine finds, or the
 * processor alone. */
export type AgentLocalPlacement = "auto" | "cpu_only";
/**
 * The local engine and placement stored beside the model lists, with the
 * revision a change sends back: the lists' own revision, as one record holds
 * both; or the same record unreadable. Either carries the engines and the
 * placements the service offers, in its order: the window offers exactly
 * those and lists none of its own.
 */
export type AgentLocalEngine =
  | {
      state: "readable";
      engine: AgentLocalEngineToken;
      placement: AgentLocalPlacement;
      choices: AgentLocalChoices;
      revision: string;
    }
  | {
      state: "unreadable";
      choices: AgentLocalChoices;
      revision: string;
    };

/** The engines and the placements the service offers, each in its order. */
export type AgentLocalChoices = {
  engine: AgentLocalEngineToken[];
  placement: AgentLocalPlacement[];
};

// ---------------------------------------------------------------------------
// Command table
// ---------------------------------------------------------------------------

/**
 * Every app command with JSON arguments: its arguments (all carrying the
 * token) and the value it resolves with. A refused call rejects with a
 * `HostFailure`. Commands that return nothing resolve with `null`.
 * `terminal_write` takes a raw body instead: see `TerminalWriteBody`.
 */
export interface HostCommands {
  user_profile_read: {
    args: { language: string };
    result: import("../shell/userProfile").UserProfile;
  };
  /** The household the profile states, in the product's words and at one
   * profile revision. Rejects with `{ code }`: `not_signed_in` or
   * `unavailable`. */
  user_profile_household: {
    args: { language: string };
    result: import("../shell/profileHousehold").ProfileHousehold;
  };
  /** Which leaves one person with unsaved answers is asked, resolved by the
   * product. The draft is a hidden input: no value of it is stored, logged or
   * echoed. Rejects with `{ code }`: `not_signed_in`, `unavailable` or
   * `invalid_household_draft` (with `refusal_words`). */
  user_profile_household_draft: {
    args: {
      language: string;
      draft: import("../shell/profileHousehold").HouseholdDraft;
    };
    result: import("../shell/profileHousehold").HouseholdDraftAnswer;
  };
  /** What `profile` states for the imputation election of `taxYear`, with
   * the setup wizard's own questions and words in `language`. */
  user_profile_imputation_election: {
    args: { profile: string; taxYear: number; language: string };
    result: import("../shell/profileHousehold").ImputationElection;
  };
  profile_censo_readiness: {
    args: { profile: string };
    result: import("../shell/profileCenso").CensoReadiness;
  };
  profile_censo_observe: { args: { updates: Channel<null> }; result: number };
  profile_censo_unobserve: { args: { subscription: number }; result: null };
  profile_censo_start: {
    args: { profile: string };
    result: import("../shell/profileCenso").CensoSnapshot;
  };
  profile_censo_status: {
    args: { profile: string; operation: string };
    result: import("../shell/profileCenso").CensoSnapshot;
  };
  profile_censo_answer: {
    args: {
      profile: string;
      operation: string;
      reviewDigest: string | null;
      decision: import("../shell/profileCenso").CensoDecision;
    };
    result: import("../shell/profileCenso").CensoSnapshot;
  };
  user_profile_change: {
    args: { change: import("../shell/userProfile").ProfileChange };
    result: null;
  };
  user_profile_observe: { args: { updates: Channel<null> }; result: number };
  user_profile_unobserve: { args: { subscription: number }; result: null };
  /** A token and the name of the certificate file picked in the native
   * dialog, never its path; null when the dialog is closed unchosen. A file
   * that is not a PKCS#12 certificate (.p12 or .pfx) rejects with `invalid`. */
  profile_aeat_certificate_pick: {
    args: Authorized;
    result: import("../shell/userProfile").AeatCertificate | null;
  };
  /**
   * Raw body only: one UTF-8 JSON object with `profile_id`, `provider` and
   * `password`, which the host sends to the runtime on its secret frame and
   * keeps nowhere. A refusal rejects with `{ code }`, one of `invalid`,
   * `not_signed_in`, `refused`, `conflict`, `unknown`, `saved_unread` and
   * `unavailable`. `unknown` and `saved_unread` mean the save was submitted
   * and its outcome was not confirmed, and it is never retried.
   */
  profile_aeat_credential_save: { args: Authorized; result: null };
  /** What was brought from AEAT, area by area, from the profile's own
   * records; it reaches no network. */
  aeat_sync_status: {
    args: { language: string };
    result: import("../shell/aeatSync").AeatSyncStatus;
  };
  aeat_sync_observe: { args: { updates: Channel<null> }; result: number };
  aeat_sync_unobserve: { args: { subscription: number }; result: null };
  /** Asks the host to bring the named areas, each over every year the
   * backend serves; while a run still goes on, the request reattaches to it.
   * A rejection carries `{ code }`: `unknown` means the request was
   * submitted and its outcome was not confirmed, and it is never retried. */
  aeat_sync_start: {
    args: {
      profile: string;
      request: import("../shell/aeatSync").AeatSyncStart;
    };
    result: null;
  };
  /** What the last reads came to, per kind of data, with the filed
   * declarations set against the profile's records; no network. */
  aeat_sync_results: {
    args: { profile: string; language: string };
    result: Omit<
      import("../shell/aeatSyncResults").AeatSyncResults,
      "notifications"
    >;
  };
  /** The notification rows with their read state, without identifiers. */
  aeat_sync_notifications: {
    args: { profile: string };
    result: import("../shell/aeatSyncResults").NotificationRow[];
  };
  /** Reads one kind of data again, or one failed part of it. A rejection
   * carries `{ code }`; `unknown` is never retried. */
  aeat_sync_retry: {
    args: {
      profile: string;
      area: import("../shell/aeatSync").AeatSyncAreaId;
      item: number | null;
      /** True once the person was told the part may already have been
       * brought; only then is a part with an unknown outcome read again. */
      acknowledgedUnknown?: boolean;
    };
    result: null;
  };
  /** The update now going on or last ended: each kind of data with its
   * parts and their outcomes; null before any. */
  aeat_sync_progress: {
    args: { profile: string };
    result: import("../shell/aeatSyncRun").AeatSyncRunSnapshot | null;
  };
  /** Lets the part in progress settle and starts nothing further. */
  aeat_sync_stop: { args: { profile: string }; result: null };
  /** Carries a paused update on from where it stopped, once the person signed
   * in again. */
  aeat_sync_resume: { args: { profile: string }; result: null };
  /** A token and the name of the Borrador PDF picked in the native dialog;
   * null when it is closed without a choice. Never a path. */
  aeat_sync_borrador_pick: {
    args: Record<never, never>;
    result: import("../shell/aeatSyncResults").BorradorFile | null;
  };
  /** Imports the picked Borrador PDF into the profile for the filing `year`
   * the person chose from the years the host served; without one the host
   * refuses with `invalid`. A rejection `unknown` means the import may have
   * been kept. */
  aeat_sync_borrador_import: {
    args: { profile: string; file: string; year?: number };
    result: import("../shell/aeatSyncResults").BorradorImportResult;
  };
  /** The Borrador 100 drafts the profile holds, as the full human read
   * serves them. It reaches no network. */
  aeat_sync_borrador_read: {
    args: {
      profile: string;
      selector: import("../shell/borrador").BorradorSelector;
    };
    result: import("../shell/borrador").BorradorRead;
  };
  /** The same drafts without each capture's provenance. */
  aeat_sync_borrador_query: {
    args: {
      profile: string;
      selector: import("../shell/borrador").BorradorSelector;
    };
    result: import("../shell/borrador").BorradorRead;
  };
  /** The year's newest readable draft beside the saved Modelo 100
   * calculation, in `language`. It changes no record. */
  aeat_sync_borrador_compare: {
    args: { profile: string; year: number; language: string };
    result: import("../shell/borrador").BorradorComparison;
  };
  /** What an update needs before it reads AEAT: the secure browser's row and
   * whether the profile has AEAT access. It reaches no network. */
  aeat_sync_prepare: {
    args: Record<string, never>;
    result: import("../shell/aeatSyncPrepare").AeatSyncPrepared;
  };
  /** Signs in to AEAT with the profile's way, reusing a valid session.
   * `progress` is told when it waits on the person's phone. A rejection
   * carries `{ code }`: `needs_access`, `cancelled`, `refused` or
   * `unavailable`. */
  aeat_sync_sign_in: {
    args: {
      progress: Channel<import("../shell/aeatSyncPrepare").AeatSignInStage>;
    };
    result: null;
  };
  /** Stops a sign-in that waits on the person's phone. */
  aeat_sync_sign_in_cancel: { args: Record<string, never>; result: null };
  /** Counts of the last notifications capture; no row reaches the window. */
  profile_views_notifications: {
    args: Authorized;
    result: import("../shell/views").NotificationsSummary;
  };
  /** The filing calendar for an inclusive range of at most about a year. */
  profile_views_calendar: {
    args: Authorized<{ from: string; to: string; language: string }>;
    result: import("../shell/views").FilingCalendar;
  };
  /** Submits one admitted ledger operation with its request, without the
   * profile, and follows it until it settles or waits on the person. A
   * failure rejects with `LedgerFailure`. */
  ledger_submit: {
    args: Authorized<{
      definition: import("../shell/ledger").LedgerDefinitionId;
      /** A JSON object: the definition's registered request. */
      payload: object;
    }>;
    result: import("../shell/ledger").LedgerOutcome;
  };
  /** Where an operation this window submitted stands, without waiting. */
  ledger_observe: {
    args: Authorized<{ operation: string }>;
    result: import("../shell/ledger").LedgerOutcome;
  };
  ledger_review: {
    args: Authorized<{ operation: string }>;
    result: import("../shell/ledger").LedgerReview;
  };
  /** Refused with `review_changed` unless `reviewDigest` is the digest of
   * the review the window read last for that operation. */
  ledger_answer: {
    args: Authorized<{
      operation: string;
      reviewDigest: string;
      decision: import("../shell/ledger").LedgerDecision;
    }>;
    result: import("../shell/ledger").LedgerOutcome;
  };
  ledger_cancel: {
    args: Authorized<{ operation: string; revision: number }>;
    result: import("../shell/ledger").LedgerOutcome;
  };
  /** Tokens for the files picked in the native dialog; never a path. */
  ledger_files_pick: {
    args: Authorized<{
      purpose: Exclude<import("../shell/ledger").FilePurpose, "export">;
      pick: import("../shell/ledger").FilePick;
      filterLabel: string;
    }>;
    result: import("../shell/ledger").FilePicks;
  };
  ledger_files_save: {
    args: Authorized<{
      format: import("../shell/ledger").LedgerExportFormat;
      filterLabel: string;
      suggestedName: string | null;
    }>;
    result: import("../shell/ledger").FilePicks;
  };
  /** Shows an exported file in the system file manager; the path never
   * reaches the window. */
  ledger_files_reveal: {
    args: Authorized<{ token: import("../shell/ledger").FileToken }>;
    result: null;
  };
  ledger_files_forget: {
    args: Authorized<{ tokens: import("../shell/ledger").FileToken[] }>;
    result: null;
  };
  ledger_drop_observe: {
    args: Authorized<{
      purpose: Exclude<import("../shell/ledger").FilePurpose, "export">;
      updates: Channel<import("../shell/ledger").LedgerDropSignal>;
    }>;
    result: number;
  };
  ledger_drop_unobserve: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  /** Raw body only: the bytes of `ownAccountChange`, the one route for an
   * own account's number and bank block. */
  ledger_own_account: {
    args: Authorized;
    result: import("../shell/ledger").LedgerOutcome;
  };
  /** Every row of the signed-in profile's declarations list. */
  modelo_declarations: {
    args: Authorized<{
      outputLanguage: import("../shell/modeloContract/modelo").OutputLanguage;
    }>;
    result: import("../shell/modeloContract/modeloDeclarations").ModeloDeclarationsListProjectionV1;
  };
  /** The declarations and works of the signed-in profile that match a query,
   * said in the output language. */
  modelo_declarations_search: {
    args: Authorized<{
      query: string;
      outputLanguage: import("../shell/modeloContract/modelo").OutputLanguage;
      limit?: number;
    }>;
    result: import("../shell/modeloContract/modeloDeclarations").ModeloDeclarationsSearchResultV1;
  };
  /** One declaration's form, with its admitted edit baseline or refusal. */
  modelo_form: {
    args: Authorized<{
      workUnitId: string;
      outputLanguage: import("../shell/modeloContract/modelo").OutputLanguage;
    }>;
    result: import("../shell/modeloContract/modeloWorkForm").ModeloWorkbenchFormProjectionV1;
  };
  modelo_casilla_help: {
    args: Authorized<{
      workUnitId: string;
      casillaId: string;
      registryRevisionId: string;
      calculationRevisionId: string | null;
      outputLanguage: import("../shell/modeloContract/modelo").OutputLanguage;
    }>;
    result: import("../shell/modeloContract/modeloWorkCasillaHelp").ModeloCasillaHelpProjectionV1;
  };
  /** Submits one admitted modelo operation with its request, without the
   * profile. `workUnit` names the form's declaration for a definition whose
   * subject is a stored record, and is absent for every other. A failure
   * rejects with `LedgerFailure`. */
  modelo_submit: {
    args: Authorized<{
      definition: import("../shell/modelo").ModeloDefinitionId;
      /** A JSON object: the definition's registered request. */
      payload: object;
      workUnit?: string;
    }>;
    result: import("../shell/ledger").LedgerOutcome;
  };
  /** Raw body only, one command per definition: the bytes of
   * `modeloEditBody`, at most `RELAY_PAYLOAD_LIMIT`. */
  modelo_edit_preflight: {
    args: Authorized;
    result: import("../shell/ledger").LedgerOutcome;
  };
  modelo_edit_apply: {
    args: Authorized;
    result: import("../shell/ledger").LedgerOutcome;
  };
  modelo_observe: {
    args: Authorized<{ operation: string }>;
    result: import("../shell/ledger").LedgerOutcome;
  };
  modelo_review: {
    args: Authorized<{ operation: string }>;
    result: import("../shell/ledger").LedgerReview;
  };
  /** Refused with `review_changed` unless `reviewDigest` is the digest of
   * the review the window read last for that operation. */
  modelo_answer: {
    args: Authorized<{
      operation: string;
      reviewDigest: string;
      decision: import("../shell/ledger").LedgerDecision;
    }>;
    result: import("../shell/ledger").LedgerOutcome;
  };
  modelo_cancel: {
    args: Authorized<{ operation: string; revision: number }>;
    result: import("../shell/ledger").LedgerOutcome;
  };
  /** A token for the one file picked in the native dialog; never a path. */
  modelo_files_pick: {
    args: Authorized<{
      purpose: import("../shell/modelo").ModeloFilePurpose;
      filterLabel: string;
    }>;
    result: import("../shell/ledger").FilePicks;
  };
  modelo_files_save: {
    args: Authorized<{
      format: import("../shell/modelo").ModeloSaveFormat;
      filterLabel: string;
      suggestedName: string | null;
    }>;
    result: import("../shell/ledger").FilePicks;
  };
  modelo_files_forget: {
    args: Authorized<{ tokens: import("../shell/ledger").FileToken[] }>;
    result: null;
  };
  /** Shows a saved file in the system file manager; the path never reaches
   * the window. */
  modelo_files_reveal: {
    args: Authorized<{ token: import("../shell/ledger").FileToken }>;
    result: null;
  };
  startup_begin: { args: Authorized; result: void };
  startup_status: { args: Authorized; result: StartupProgress };

  runtime_attendance_inventory: {
    args: Authorized;
    result: {
      kind: "attendance_inventory";
      candidates: import("../shell/host").AttendanceCandidate[];
    };
  };
  runtime_attendance_decide: {
    args: Authorized & { attendanceId: string; approve: boolean };
    result: {
      kind: "attendance_decided";
      attendance_id: string;
      approved: boolean;
    };
  };
  runtime_attendance_subscribe: {
    args: Authorized<{ updates: Channel<null> }>;
    result: number;
  };
  runtime_attendance_unsubscribe: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  shell_window_action: {
    args: Authorized<{ action: WindowAction }>;
    result: null;
  };
  desktop_frontend_diagnostic: {
    args: Authorized<{
      report: {
        event:
          | "command_rejected"
          | "uncaught_error"
          | "unhandled_rejection"
          | "react_error"
          | "console";
        level: LogLevel;
        command: string | null;
        code: string | null;
        dropped: number;
        line?: number;
        column?: number;
        /** The backend's closed code beside a relay failure's `code`. */
        reason?: string;
        /** The message's authored shape with every value taken out. */
        template?: string;
        /** The script the first stack frame names, by file name. */
        module?: string;
      };
    }>;
    result: null;
  };
  shell_window_subscribe: {
    args: Authorized<{ updates: Channel<WindowPresentation> }>;
    result: number;
  };
  shell_window_unsubscribe: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  /** A close the system raised asks the page first, while it listens. */
  shell_close_guard_subscribe: {
    args: Authorized<{ requests: Channel<null> }>;
    result: number;
  };
  shell_close_guard_unsubscribe: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  manager_install: {
    args: Authorized<{ scope: "user" | "machine" }>;
    result: "dispatched" | "unsupported";
  };
  manager_start: {
    args: Authorized;
    result: "dispatched" | "unsupported";
  };
  manager_status: { args: Authorized; result: ManagerStatus };
  manager_subscribe: {
    args: Authorized<{ updates: Channel<ManagerSignal> }>;
    result: number;
  };
  manager_unsubscribe: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  sign_in_status: { args: Authorized; result: SignInStatus };
  sign_in_activity: { args: Authorized; result: void };
  sign_in_subscribe: {
    args: Authorized<{ updates: Channel<SignInSignal> }>;
    result: number;
  };
  sign_in_unsubscribe: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  sign_out: { args: Authorized; result: SignOutResult };
  /** Needs no password, session or runtime, and changes nothing. */
  profile_list: { args: Authorized; result: ProfileList };
  profile_delete_review: {
    args: Authorized & { name: string };
    result: ProfileDeleteReview;
  };
  profile_delete: {
    args: Authorized & {
      review: ProfileDeleteReview;
      confirmation: string;
      acknowledged: boolean;
    };
    result: null;
  };
  /** Raw body only: see PasswordChangeResult. */
  profile_password_change: { args: Authorized; result: PasswordChangeResult };
  desktop_language_read: { args: Authorized; result: DesktopLanguage };
  desktop_language_set: {
    args: Authorized<{ language: string }>;
    result: DesktopLanguage;
  };
  desktop_language_observe: {
    args: Authorized<{ updates: Channel<DesktopLanguage> }>;
    result: number;
  };
  desktop_language_unobserve: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  desktop_environment: {
    args: Authorized;
    result: DesktopEnvironment;
  };
  about_info: { args: Authorized; result: AboutInfo };
  /** The changes the previous close ended before they reported, once. */
  previous_close: { args: Authorized; result: number };
  /** Each setup command refuses with `SetupRefusal` or a `HostFailure`. */
  desktop_setup_read: { args: Authorized; result: DesktopSetup };
  /** Starts a status read; "quick" reads local facts only, "full" also
   * reaches the network and exercises each item. */
  desktop_setup_check: {
    args: Authorized<{ mode: SetupCheckMode }>;
    result: DesktopSetup;
  };
  /** Starts a full check of `items`, or of every item when null. */
  desktop_setup_verify: {
    args: Authorized<{ items: SetupItemId[] | null }>;
    result: DesktopSetup;
  };
  /** Plans setup of one `item`; the plan then awaits an answer in that
   * item's run's `review`. An explicit download, of the local AI alone, is
   * validated against the current catalogue independently of document tasks;
   * otherwise the host reads saved model selections. Admission failure
   * refuses the start. A setup of the item already running is joined; another
   * item's setup never refuses it.
   * `resume` is the person's Resume click after an interruption: when the
   * new plan is exactly the one approved before, it is approved again
   * without a second review; any other plan awaits an answer as usual.
   * `reinstall` is the served reinstall of the local AI's program: its
   * downloaded program is installed afresh, never with a resume or a
   * download. */
  desktop_setup_start: {
    args: Authorized<{
      item: SetupItemId;
      resume: boolean;
      reinstall?: boolean;
      download?: SetupModelDownload;
    }>;
    result: DesktopSetup;
  };
  /** Answers the plan whose digest the review showed; a changed plan
   * refuses with `plan_changed`. */
  desktop_setup_answer: {
    args: Authorized<{
      operationId: string;
      planDigest: string;
      decision: "apply" | "reject";
    }>;
    result: DesktopSetup;
  };
  desktop_setup_cancel: {
    args: Authorized<{ operationId: string }>;
    result: DesktopSetup;
  };
  /** Removes one local model no role selects, named as a selection names it. */
  desktop_setup_remove_model: {
    args: Authorized<{ model: string }>;
    result: DesktopSetup;
  };
  /** Removes the browser, or the local AI or its program alone, from this
   * computer. */
  desktop_setup_remove: {
    args: Authorized<{ removal: SetupRemoval }>;
    result: DesktopSetup;
  };
  /** Opens Google's own sign-in page for the signed-in profile; `google`
   * follows the attempt. */
  desktop_google_sign_in: { args: Authorized; result: DesktopSetup };
  /** Removes the profile's stored Google sign-in. */
  desktop_google_sign_out: { args: Authorized; result: DesktopSetup };
  desktop_setup_observe: {
    args: Authorized<{ updates: Channel<DesktopSetup> }>;
    result: number;
  };
  desktop_setup_unobserve: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  /**
   * Starts a session of `kind`, replacing one that already exited. Refuses
   * `session_unavailable` while a live session of that kind exists, and
   * when the page that sent the request was reloaded or replaced before the
   * session started, in which case any session it started is settled first.
   * Refuses `invalid_arguments` for a size outside 2 to 1000.
   */
  terminal_open: {
    args: Authorized<TerminalOpenArguments>;
    result: TerminalOpened;
  };
  terminal_ack: {
    args: Authorized<TerminalAck>;
    result: null;
  };
  /** Refuses `invalid_arguments` for a size outside 2 to 1000. */
  terminal_resize: {
    args: Authorized<TerminalResize>;
    result: null;
  };
  /**
   * Stops the session and waits up to three seconds for it to settle. A
   * session that misses the bound stays owned and the call rejects, with
   * `cleanup_failed` or the termination failure; a later close retries.
   */
  terminal_close: {
    args: Authorized<TerminalClose>;
    result: TerminalClosed;
  };
  /** `after` is the last `OutputChunk.sequence` seen; 0 for everything. */
  diagnostics_snapshot: {
    args: Authorized<{ after: number }>;
    result: DiagnosticsSnapshot;
  };
  logs_subscribe: {
    args: Authorized<{ records: Channel<LogBatch> }>;
    result: LogSubscription;
  };
  logs_export: {
    args: Authorized<{ text: string }>;
    result: string;
  };
  logs_copy: {
    args: Authorized<{ text: string }>;
    result: null;
  };
  logs_reveal: {
    args: Authorized;
    result: null;
  };
  /** Refuses an unknown subscription with `invalid_arguments`. */
  logs_unsubscribe: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  /**
   * Hands the URL to the system's handler. Accepts an `https://` URL with a
   * non-empty host and no user information, or a `mailto:` URL with an
   * address part, no fragment, and only the header fields `subject`, `body`,
   * `cc` and `bcc`, each written `name=value` with the name unencoded (any
   * other field, such as `attach` or `to`, is refused). The text must be at
   * most 8,192 printable ASCII characters
   * without a backslash, and the scheme lowercase. Everything else is
   * refused with `invalid_arguments`; a handler that cannot start rejects
   * with `spawn_failed`.
   */
  open_external: {
    args: Authorized<{ url: string }>;
    result: null;
  };
  /** The bytes of the raw frame a channel message named, as binary, handed
   * over once to the document they were sent to. An unknown, taken or dropped
   * frame is refused with `invalid_arguments`. */
  shell_channel_frame: {
    args: Authorized<{ frame: string }>;
    result: ArrayBuffer;
  };
  /**
   * Refuses with `output_limit` when the clipboard text exceeds 1 MiB in
   * UTF-8; the text is never truncated.
   */
  shell_clipboard_read: {
    args: Authorized;
    result: ClipboardText;
  };
  /** Refuses `text` over 1 MiB in UTF-8 with `invalid_arguments`. */
  shell_clipboard_write: {
    args: Authorized<ClipboardText>;
    result: null;
  };
  /**
   * The agent host. Every agent command refuses with `{ code }`: the
   * service's own refusal while it is not ready, `agent_reply_unknown` for
   * a reply this host is not watching, and `agent_conversation_unavailable`
   * for any conversation, which is not yet named by its run chain.
   */
  agent_status: { args: Authorized; result: AgentServiceStatus };
  agent_retry: { args: Authorized; result: null };
  agent_status_subscribe: {
    args: Authorized<{ updates: Channel<AgentServiceStatus> }>;
    result: number;
  };
  agent_status_unsubscribe: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  /** cadrumo-agent's catalog, unchanged, less the lanes the profile turned
   * off; while no agent is ready, its declared catalog in an envelope. */
  agent_provider_catalog: { args: Authorized; result: AgentCatalogAnswer };
  /** The models the person added to the local lanes' lists, as the agent
   * service stores them. */
  agent_local_models: { args: Authorized; result: AgentLocalModels };
  /** Adds a model by name to a local lane's list at the revision read. A
   * refusal is `agent_local_models_<reason>` for the service's reasons, such
   * as `agent_local_models_full`, or a column code. */
  agent_local_model_add: {
    args: Authorized<{ lane: string; model: string; expectedRevision: string }>;
    result: AgentLocalModels;
  };
  /** Takes an added model off a local lane's list at the revision read. */
  agent_local_model_remove: {
    args: Authorized<{ lane: string; model: string; expectedRevision: string }>;
    result: AgentLocalModels;
  };
  /** Removes the list record, readable or not, at the revision read. */
  agent_local_models_reset: {
    args: Authorized<{ expectedRevision: string }>;
    result: AgentLocalModels;
  };
  /** The local engine and placement, as the agent service stores them. */
  agent_local_engine: { args: Authorized; result: AgentLocalEngine };
  /** Stores the local engine and placement at the revision read; the service
   * retires and restarts the assistant when either changes. A refusal is
   * `agent_local_models_<reason>` (the same service reasons as the model
   * list) or a column code. */
  agent_local_engine_choose: {
    args: Authorized<{
      engine: AgentLocalEngineToken;
      placement: AgentLocalPlacement;
      expectedRevision: string;
    }>;
    result: AgentLocalEngine;
  };
  /** Stores the model documents are read with, on any lane the catalogue
   * reports, at the revision read. */
  agent_reading_model_choose: {
    args: Authorized<{ lane: string; model: string; expectedRevision: string }>;
    result: AgentLocalModels;
  };
  /** One model's licence text, from the ready agent's licence route. */
  agent_model_licence: {
    args: Authorized<{ provider: string; transport: string; model: string }>;
    result: AgentModelLicence;
  };
  /** cadrumo-agent's skills, as `GET /v1/skills` lists them, unchanged. */
  agent_skills: { args: Authorized; result: unknown };
  /** One skill with its SKILL.md, as `GET /v1/skills/{name}` serves it. A
   * name outside the skill grammar is refused as `agent_invalid_request`
   * before the agent is asked, and an unknown one as
   * `agent_gateway_skill_not_found`. */
  agent_skill: { args: Authorized<{ name: string }>; result: unknown };
  /** The agent's checks of one skill, from `POST /v1/skills/{name}/verify`. */
  agent_skill_verify: { args: Authorized<{ name: string }>; result: unknown };
  agent_conversation_start: {
    args: Authorized;
    result: AgentConversationRecord;
  };
  /** One trimmed line of 1 to 200 characters, else `agent_invalid_request`. */
  agent_conversation_rename: {
    args: Authorized<{ conversationId: string; title: string }>;
    result: null;
  };
  /** Deletes the conversation, every run of it and the documents stored
   * for it; `agent_conversation_delete_incomplete` when some remain, which a
   * repeated request finishes. */
  agent_conversation_delete: {
    args: Authorized<{ conversationId: string }>;
    result: null;
  };
  /** Archives every settled run together, keeping the conversation readable. */
  agent_conversation_archive: {
    args: Authorized<{ conversationId: string }>;
    result: null;
  };
  /** Opens the host's file picker and stores what is picked in the
   * conversation's storage, following each upload on `updates`. */
  agent_attach: {
    args: Authorized<{
      conversationId: string;
      filterLabel: string;
      updates: Channel<AgentUploadEvent>;
      dropId?: string;
    }>;
    result: AgentUploadPick[];
  };
  agent_drop_observe: {
    args: Authorized<{ updates: Channel<AgentDropSignal> }>;
    result: number;
  };
  agent_drop_unobserve: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  agent_documents_remove: {
    args: Authorized<{ conversationId: string; name?: string }>;
    result: null;
  };
  agent_attachment_policy: { args: Authorized; result: AgentAttachmentPolicy };
  agent_send: {
    args: Authorized<{ request: AgentSendRequest }>;
    result: AgentSendResult;
  };
  agent_cancel: { args: Authorized<{ replyId: string }>; result: null };
  agent_pending: {
    args: Authorized<{ conversationId: string }>;
    result: {
      questionnaires: AgentQuestionnaire[];
      approvals: AgentApproval[];
    };
  };
  agent_questions_answer: {
    args: Authorized<{
      questionnaire: Pick<AgentQuestionnaire, "reply_id" | "request_id">;
      answer: AgentQuestionnaireAnswer;
    }>;
    result: AgentAnswerResult;
  };
  /** Answers a tool approval; Cadrumo reviews are not served. */
  agent_approval_decide: {
    args: Authorized<{
      approval: Pick<AgentApproval, "reply_id" | "request_id">;
      optionId: string;
    }>;
    result: null;
  };
  /** What the service says the card shows for a parked attachment read. */
  agent_attachment_card: {
    args: Authorized<{
      approval: Pick<AgentApproval, "reply_id" | "request_id">;
    }>;
    result: AgentAttachmentCard;
  };
  /** Puts the person's answer to the service; the request is answered only once released. */
  agent_attachment_release: {
    args: Authorized<{
      approval: Pick<AgentApproval, "reply_id" | "request_id">;
      optionId: string;
      scope: AgentAttachmentScope | null;
    }>;
    result: AgentAttachmentRelease;
  };
  agent_attachment_grants: {
    args: Authorized<Record<string, never>>;
    result: AgentAttachmentGrants;
  };
  agent_attachment_grant_revoke: {
    args: Authorized<{ grantId: string }>;
    result: { kind: "revoked" } | AgentAttachmentRefusal;
  };
  agent_observe: {
    args: Authorized<{
      conversationId: string;
      events: Channel<AgentStreamEvent>;
    }>;
    result: number;
  };
  agent_unobserve: {
    args: Authorized<{ subscription: number }>;
    result: null;
  };
  agent_conversations: {
    args: Authorized;
    result: AgentConversationRecord[];
  };
  agent_snapshot: {
    args: Authorized<{ conversationId: string }>;
    result: AgentSnapshot;
  };
  agent_history: {
    args: Authorized<{ conversationId: string }>;
    result: AgentTurnRecord[];
  };
  /** One page of the documents stored for a conversation, by name. */
  agent_documents: {
    args: Authorized<{ query: AgentDocumentsQuery }>;
    result: AgentDocumentPage;
  };
  // provider_settings_set takes the key as a raw body, with the provider,
  // revision and base URL in headers, as sign_in_submit takes a password.
  provider_settings_status: {
    args: Authorized;
    result: ProviderSettingsAnswer;
  };
  provider_settings_remove: {
    args: Authorized<{ provider: string; revision: string }>;
    result: ProviderSettingsRecord;
  };
  provider_settings_turn_on: {
    args: Authorized<{ provider: string; revision: string }>;
    result: ProviderSettingsRecord;
  };
  provider_settings_reset: {
    args: Authorized<{ provider: string; revision: string }>;
    result: ProviderSettingsRecord;
  };
  // An attended provider sign-in is transient. Its URL and device code are
  // returned only while the person is completing this attempt.
  provider_sign_in_start: {
    args: Authorized<{
      provider: string;
      revision: string;
      method: "browser" | "device" | "browser-code";
    }>;
    result: ProviderSignInSnapshot;
  };
  provider_sign_in_status: {
    args: Authorized<{ attemptId: string }>;
    result: ProviderSignInSnapshot;
  };
  provider_sign_in_cancel: {
    args: Authorized<{ attemptId: string }>;
    result: ProviderSignInSnapshot;
  };
  // provider_sign_in_submit_code takes a raw secret body and attempt-id header.
  provider_sign_in_submit_code: {
    args: Authorized;
    result: ProviderSignInSnapshot;
  };
  // The keys issued to agents outside Cadrumo. None carries a password or a
  // key; issuing is refused with `issue_unavailable` for now.
  agent_access_list: {
    args: Authorized;
    result: AgentAccessAnswer;
  };
  agent_access_issue: {
    args: Authorized<{ taxValues: boolean }>;
    result: { credential_reference: string };
  };
  agent_access_revoke: {
    args: Authorized<{ grantId: string }>;
    result: { cleanup_pending: boolean };
  };
  // The Sede view: one view at a time, relayed on the channel `sede_view_open`
  // is given. The window never names an address; `sede_view_open_external`
  // opens the page the host holds.
  sede_view_open: {
    args: Authorized<{
      cssWidth: number;
      cssHeight: number;
      scale: number;
      messages: Channel<SedeViewDelivery>;
    }>;
    result: { view: number };
  };
  sede_view_close: { args: Authorized<{ view: number }>; result: null };
  sede_view_input: {
    args: Authorized<{ view: number; event: SedeViewInput }>;
    result: null;
  };
  sede_view_navigate: {
    args: Authorized<{ view: number; verb: SedeViewVerb }>;
    result: null;
  };
  sede_view_clipboard: {
    args: Authorized<{ view: number; action: SedeClipboardAction }>;
    result: null;
  };
  sede_view_resize: {
    args: Authorized<{
      view: number;
      cssWidth: number;
      cssHeight: number;
      scale: number;
    }>;
    result: null;
  };
  /** One for each image message received, drawn or not. */
  sede_view_credit: { args: Authorized<{ view: number }>; result: null };
  sede_view_dialog: {
    args: Authorized<{
      view: number;
      dialogId: number;
      accept: boolean;
      promptText?: string;
    }>;
    result: null;
  };
  /** With `save`, the native save dialog asks where; the answer waits for it. */
  sede_view_download_answer: {
    args: Authorized<{ view: number; transferId: number; save: boolean }>;
    result: { saving: boolean };
  };
  /** With `choose`, the native open dialog asks which files; the answer
   * waits for it. */
  sede_view_file_chooser_answer: {
    args: Authorized<{ view: number; chooserId: number; choose: boolean }>;
    result: { supplied: number };
  };
  sede_view_open_external: {
    args: Authorized<{ view: number }>;
    result: null;
  };
}

/** Native presentation only; no profile or runtime authority. */
export type WindowPresentation = {
  maximized: boolean;
  fullscreen: boolean;
  /** Who draws the minimise, maximise and close controls. */
  chrome: "custom" | "native";
  /** Where the system draws the controls: the header row's height and the
   * leading inset that clears them, in CSS pixels, as the host seated them. */
  nativeControls: { height: number; inset: number } | null;
};

export type WindowAction =
  | "minimize"
  | "toggle_maximize"
  | "toggle_fullscreen"
  | "leave_fullscreen"
  | "close"
  | "drag"
  | "focus"
  /** The page's answers to a close it was asked about. */
  | "close_now"
  | "keep_open";

export type HostCommand = keyof HostCommands;

export type HostArguments<C extends HostCommand> = HostCommands[C]["args"];

export type HostResult<C extends HostCommand> = HostCommands[C]["result"];
