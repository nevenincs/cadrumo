// The desktop shell's published IPC contract: the app commands the Rust host
// registers, the frames its channels carry, and the postMessage bridge between
// the shell document and the documentation frame.
//
// Types, plus the terminal frame tags as constants; nothing else here runs.
// Field names and casing follow the host's serde output exactly.

import type { Channel } from "@tauri-apps/api/core";
import type {
  AgentAnswerResult,
  AgentApproval,
  AgentProviderCatalog,
  AgentQuestionnaire,
  AgentQuestionnaireAnswer,
  AgentSendRequest,
  AgentUploadEvent,
  AgentUploadPick,
  AgentSendResult,
  AgentServiceStatus,
  AgentStreamEvent,
} from "../shell/agentSession";
import type { AgentAccessAnswer } from "../shell/agentAccess";
import type {
  AgentSnapshot,
  AgentConversationRecord,
  AgentDocumentPage,
  AgentDocumentsQuery,
  AgentTurnRecord,
} from "../shell/agentViews";
import type {
  ProviderSettingsAnswer,
  ProviderSettingsRecord,
  ProviderSignInSnapshot,
} from "../shell/providerSettings";

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
  | "read_failed"
  | "write_failed"
  | "resize_failed"
  | "cleanup_failed"
  | "session_unavailable"
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
// about_info
// ---------------------------------------------------------------------------

/** One name with its version, ordered by name. */
export type AboutNamed = { name: string; version: string };

/** A native binary of the installed package. Every field the package does
 * not state is null. */
export type AboutComponent = {
  name: string | null;
  role: string | null;
  path: string | null;
  version: string | null;
  build_id: string | null;
  build_type: string | null;
};

/** What this installation is: the installed package manifest's statement,
 * plus the desktop binary's own compile-time identity. A null is a value the
 * package or the build did not state; the shell says it is unavailable. */
export type AboutInfo = {
  product: string | null;
  display_version: string | null;
  version: string | null;
  build_id: string | null;
  build_type: string | null;
  build_date: string | null;
  channel: string | null;
  target: string | null;
  /** The bundled CPython runtime's version. */
  python: string | null;
  desktop: {
    version: string | null;
    build_id: string | null;
    build_type: "debug" | "release";
  };
  components: AboutComponent[];
  /** Null when the package does not bundle the agent. */
  agent: { version: string | null; dependencies: AboutNamed[] } | null;
  /** Bundled tools by name, for example `node`. */
  tools: Record<string, string>;
  distributions: AboutNamed[];
};

// ---------------------------------------------------------------------------
// desktop_environment
// ---------------------------------------------------------------------------

export type DocsLanguage = {
  /** Language code, for example `en`, `es`, `ca`, `hu`. */
  code: string;
  /**
   * The language's entry page from the docs manifest, as an absolute URL on
   * the documentation origin with its path segments percent-encoded. Use it
   * as given; do not rebuild it from `origin`.
   */
  entry: string;
};

export type DesktopLanguage = {
  language: string;
  persisted: boolean;
  profile: string | null;
  /** Monotonic host revision shared by reads, writes and observations. */
  revision: number;
};

export type DesktopEnvironment = {
  /** The output language Settings resolved for this profile. */
  outputLanguage: string;
  /** Initial minimum severity selected by the host; defaults to INFO. */
  logLevel: LogLevel;
  /** The package's statement of whether it carries the documentation. */
  docs: DesktopDocs;
};

export type DesktopDocs =
  | {
      state: "bundled";
      /** The documentation origin, computed by the host for this platform. */
      origin: string;
      languages: DocsLanguage[];
    }
  | { state: "notBundled" }
  /** Bundled, but this launch could not open it; everything else still works. */
  | { state: "unavailable" };

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

/**
 * `id` and `label` are 1 to 128 and 1 to 256 characters, `shortcut` 1 to 64,
 * none with control characters; ids are unique within one menu.
 */
export type ContextMenuAction = {
  /** Returned as `chosen`; the host namespaces it internally per popup. */
  id: string;
  /** Shown literally; an `&` is not a mnemonic marker. */
  label: string;
  /** A disabled item is shown but can never be `chosen`. */
  enabled: boolean;
  /** Display-only accelerator text shown beside the label; binds nothing. */
  shortcut?: string;
};

/** Exactly `{ separator: true }`; any other field is refused. */
export type ContextMenuSeparator = { separator: true };

export type ContextMenuItem = ContextMenuAction | ContextMenuSeparator;

/**
 * 1 to 64 items with at least one action. `x` and `y` are both present or
 * both omitted; one without the other is refused with `invalid_arguments`.
 */
export type ContextMenuRequest = {
  items: ContextMenuItem[];
} & (
  | {
      /**
       * Logical position in shell CSS pixels: for a documentation menu, the
       * iframe rect plus its border plus the relayed client coordinates, with
       * no device-pixel scaling. Finite, with a magnitude of at most 1e6.
       */
      x: number;
      y: number;
    }
  | {
      /** Omit both for a pointer-opened menu, which opens at the cursor. */
      x?: never;
      y?: never;
    }
);

/** Resolves when the native menu closes; `null` when it was dismissed. */
export type ContextMenuResult = { chosen: string | null };

// ---------------------------------------------------------------------------
// Terminals
// ---------------------------------------------------------------------------

/**
 * At most one session per kind: `console` is the platform's interactive
 * shell and `python` the packaged interpreter's REPL, both started in the
 * user's home; `tui` is the Cadrumo TUI, started in the storage root.
 */
export type TerminalKind = "console" | "python" | "tui";

/** A session id from `terminal_open`; a replaced or closed id is refused. */
export type TerminalSessionId = number;

/** Columns and rows are each an integer from 2 to 1000. */
export type TerminalSize = { cols: number; rows: number };

/**
 * Every message on a session's frame channel arrives as an `ArrayBuffer`
 * holding one frame: a tag byte, then the payload. One channel orders every
 * frame, and frames can arrive before `terminal_open` resolves.
 *
 * | Tag | Frame     | Payload                                    |
 * | --- | --------- | ------------------------------------------ |
 * | 0   | `data`    | PTY output bytes, 1 to 8192                |
 * | 1   | `started` | UTF-8 JSON `TerminalStartedPayload`        |
 * | 2   | `exited`  | UTF-8 JSON `TerminalExitedPayload`         |
 * | 3   | `failed`  | UTF-8 JSON `TerminalFailedPayload`         |
 *
 * An empty frame, an empty `data` frame, an unknown tag or a payload that is
 * not the stated JSON is malformed.
 */
export const TerminalFrameTag = {
  data: 0,
  started: 1,
  exited: 2,
  failed: 3,
} as const;

export type TerminalFrameType = keyof typeof TerminalFrameTag;
export type TerminalFrameTagValue =
  (typeof TerminalFrameTag)[TerminalFrameType];

/** The largest `data` payload, in bytes. */
export type TerminalDataLimit = 8192;

/** The `started` payload: the child's operating-system process id. */
export type TerminalStartedPayload = { pid: number };

/**
 * The `exited` payload. `code` is the child's exit code as an unsigned
 * 32-bit value, so a Windows status such as `0xC000013A` arrives as a large
 * positive number; it is `null` when the host could not read the status.
 */
export type TerminalExitedPayload = { code: number | null };

/** The `failed` payload: the serialized host failure. */
export type TerminalFailedPayload = { error: HostFailure };

/**
 * Output bytes. Only `data` payload bytes advance the offset `terminal_ack`
 * acknowledges.
 */
export type TerminalDataFrame = { type: "data"; bytes: Uint8Array };

/** The first frame of a session. */
export type TerminalStartedFrame = {
  type: "started";
} & TerminalStartedPayload;

/**
 * The last frame of a session whose child exited on its own: it follows
 * every `data` frame. A session settled by `terminal_close` or by a new
 * shell document stops delivering frames and sends no `exited`.
 */
export type TerminalExitedFrame = { type: "exited" } & TerminalExitedPayload;

/**
 * A read, write or wait failure. A read failure ends output; write and wait
 * failures are reported just before `exited`. Not itself the last frame.
 */
export type TerminalFailedFrame = { type: "failed" } & TerminalFailedPayload;

/** One decoded frame, discriminated by `type`. */
export type TerminalFrame =
  | TerminalDataFrame
  | TerminalStartedFrame
  | TerminalExitedFrame
  | TerminalFailedFrame;

export type TerminalOpenArguments = TerminalSize & {
  kind: TerminalKind;
  /** Receives the session's frames, each as an `ArrayBuffer`. */
  frames: Channel<ArrayBuffer>;
};

export type TerminalOpened = { session: TerminalSessionId };

/**
 * The cumulative count of `data` payload bytes the shell has consumed. A
 * stale offset changes nothing; an offset beyond the bytes delivered is
 * refused with `invalid_arguments`. The host stops reading the PTY once
 * 512 KiB are unacknowledged and resumes below 128 KiB, so the child blocks
 * rather than losing output.
 */
export type TerminalAck = { session: TerminalSessionId; offset: number };

export type TerminalResize = TerminalSize & { session: TerminalSessionId };

export type TerminalClose = { session: TerminalSessionId };

/** Resolves once the session has settled: its child and workers are gone. */
export type TerminalClosed = Record<never, never>;

/**
 * The headers of a `terminal_write` call, as a plain object passed as
 * `invoke`'s `headers` option. The session header is the id in decimal.
 */
export type TerminalWriteHeaders = {
  [Name in TokenHeader]: ShellToken;
} & { [Name in SessionHeader]: string };

/**
 * The body of a `terminal_write` call: raw input bytes, at most 65,536. When
 * Tauri falls back to its postMessage transport the same bytes arrive as a
 * JSON array of integers from 0 to 255, under the same limit. An empty body
 * is accepted and writes nothing. The call resolves with `null` once the
 * bytes are queued.
 *
 * Refusals: `invalid_arguments` for a missing token or session header, an
 * oversized or malformed body; `queue_full` when eight writes are already
 * pending, which is backpressure and must be retried with the same bytes;
 * `session_unavailable` once the session's input has stopped; `write_failed`
 * after an earlier write to the child failed.
 */
export type TerminalWriteBody = Uint8Array | number[];

export type TerminalWriteLimit = 65536;

// ---------------------------------------------------------------------------
// Diagnostics (diagnostics_snapshot)
// ---------------------------------------------------------------------------

export type DiagnosticsEventKind =
  | "host_started"
  | "stage_started"
  | "stage_completed"
  | "headless_selected"
  | "gui_selected"
  | "child_started"
  | "child_exited"
  | "child_terminated"
  | "helper_timing"
  | "helper_result"
  | "failure"
  | "host_stopped"
  | "window_close_requested"
  | "host_exit_requested"
  | "panic";

/** `ProcessPhase` in `native/application/src/process/status.rs`. */
export type ProcessPhase = "running" | "exited" | "terminated" | "failed";

export type OutputStream = "stdout" | "stderr" | "terminal";

/** One child process the host started; the host keeps the latest 128. */
export type ProcessStatus = {
  /** The host's own process number, distinct from the operating-system `pid`. */
  id: number;
  pid: number;
  role: ProcessRole;
  phase: ProcessPhase;
  startedMs: number;
  finishedMs: number | null;
  exitCode: number | null;
  stdoutBytes: number;
  stderrBytes: number;
  terminalBytes: number;
};

export type DiagnosticsEvent = {
  /** Monotonic identity within this diagnostics instance. */
  sequence: number;
  source: "desktop" | "manager" | "installer";
  timestampMs: number;
  hostPid: number;
  kind: DiagnosticsEventKind;
  /** The `ProcessStatus.id` the event concerns. */
  process: number | null;
  failure: HostFailure | null;
  status: ProcessStatus | null;
  stage?: "admission" | "environment" | "manager" | "window" | "shutdown";
  role?: ProcessRole;
  outcome?:
    | "ready"
    | "already_running"
    | "dispatched"
    | "skipped_unmanaged"
    | "unavailable";
  hostExitCode?: number;
  webviewFailure?: WebviewFailure;
  helperTiming?: HelperTiming;
  helperResult?: HelperResult;
  panic?: PanicFact;
};

/** `PanicFact` in `native/application/src/diagnostics/panic.rs`: never the message. */
export type PanicFact = {
  /** Crate-relative source path, without the build account's directories. */
  file: string | null;
  line: number | null;
  column: number | null;
  thread: string;
  threadId: number;
  category:
    | "option_none"
    | "result_err"
    | "index_out_of_bounds"
    | "slice_range"
    | "arithmetic_overflow"
    | "division_by_zero"
    | "borrow_conflict"
    | "lock_poisoned"
    | "no_async_runtime"
    | "nested_async_runtime"
    | "unreachable"
    | "unimplemented"
    | "assertion"
    | "allocation_failure"
    | "cannot_unwind"
    | "explicit"
    | "unclassified";
};

export type HelperResult = {
  command: string;
  executable: "cli" | "runtime" | "agent_service";
  envelopeDecode:
    "success" | "refused" | "native_refused" | "malformed" | "unavailable";
  stdoutBytes: number;
  stderrBytes: number;
  code: string | null;
  reason: string | null;
  exceptionType: string | null;
  raisedAt: string | null;
  nativeSubject: string | null;
};

/** One native helper attempt; CLI envelope decoding happens after this summary. */
export type HelperTiming = {
  helperKind: "read" | "mutation";
  outcome:
    | "admission_refused"
    | "spawn_failed"
    | "execution_failed"
    | "nonzero_exit"
    | "completed";
  admissionWaitMs: number;
  spawnMs: number | null;
  executionMs: number | null;
  cleanupMs: number | null;
  outputJoinMs: number | null;
  totalMs: number;
};

/** Closed WebView2 telemetry. No page text, URLs, paths or failed renderer PID. */
export type WebviewFailure =
  | {
      event: "process_failed";
      kind:
        | "browser_process_exited"
        | "render_process_exited"
        | "render_process_unresponsive"
        | "frame_render_process_exited"
        | "utility_process_exited"
        | "sandbox_helper_process_exited"
        | "gpu_process_exited"
        | "ppapi_plugin_process_exited"
        | "ppapi_broker_process_exited"
        | "unknown_process_exited"
        | "unrecognized"
        | null;
      kindCode: number | null;
      reason:
        | "unexpected"
        | "unresponsive"
        | "terminated"
        | "crashed"
        | "launch_failed"
        | "out_of_memory"
        | "profile_deleted"
        | "unrecognized"
        | null;
      reasonCode: number | null;
      /** Telemetry only: 259 for an unresponsive renderer means STILL_ACTIVE. */
      exitCode: number | null;
      readFailures: {
        argumentsHresult?: number;
        kindHresult?: number;
        detailsHresult?: number;
        reasonHresult?: number;
        exitCodeHresult?: number;
      };
    }
  | {
      event: "monitor_unavailable";
      operation: "dispatch" | "core_webview" | "register";
      hresult: number | null;
    };

/** Captured output, kept in memory only and bounded to 256 KiB in total. */
export type OutputChunk = {
  /** Increases by one per chunk; pass the last one seen as `after`. */
  sequence: number;
  /** The `ProcessStatus.id` that wrote the chunk. */
  process: number;
  stream: OutputStream;
  bytes: number[];
};

/** Absolute paths of the host's diagnostics log. */
export type DiagnosticsLogPaths = { current: string; lock: string };

export type DiagnosticsSnapshot = {
  /** `null` until the host has configured its log file. */
  paths: DiagnosticsLogPaths | null;
  logFailure: HostFailure | null;
  /** The latest 512 events. */
  events: DiagnosticsEvent[];
  processes: ProcessStatus[];
  /** Only chunks whose `sequence` is greater than the request's `after`. */
  output: OutputChunk[];
  /** Output bytes evicted from the capture since the host started. */
  droppedBytes: number;
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
export type SignInRefusal = {
  code: string;
  retryAfterSeconds: number | null;
  /** Safe native failure context, without exception messages or paths. */
  operation?: HostOperation;
  ioKind?: string;
  osCode?: number;
};

/** Presence only: reading this never resumes or extends a sign-in. */
export type SignInStatus = {
  supported: boolean;
  state: "present" | "absent" | "unknown";
  active_profile: string | null;
  runtimeAvailable: boolean;
  refusal: SignInRefusal | null;
};

/** Public presence and runtime/profile changes; never session authority. */
export type SignInSignal =
  | { kind: "sign-in-state"; revision: number; status: SignInStatus }
  | {
      kind: "sign-in-observation-failed";
      revision: number;
      error: HostFailure;
    };

/** Supervisor readiness is public availability, never profile authentication. */
export type ManagerStatus = {
  state:
    | "unsupported"
    | "starting"
    | "ready"
    | "recovering"
    | "waiting"
    | "stopping"
    | "stopped"
    | "failed";
  failure: HostFailure | null;
};

export type ManagerSignal =
  | { kind: "manager-state"; revision: number; status: ManagerStatus }
  | {
      kind: "manager-observation-failed";
      revision: number;
      error: HostFailure;
    };

/** sign_in_submit uses a raw UTF-8 password body and x-cadrumo-token header. */
export type SignInResult =
  | { kind: "signed-in"; status: SignInStatus }
  | ({ kind: "refused" } & SignInRefusal);

export type SignOutResult = {
  remainingAccess: {
    /** The person's saved automation setting. A sign-out keeps it; it is not
     * access. */
    automationEnabled: boolean | null;
    /** Whether a key issued for an external agent can still admit. Keys do
     * not follow the sign-in, so this is true while one can. Null when the
     * product could not say. */
    automationAccessRemains: boolean | null;
    automationRevoked: false;
  };
};

export type ProfileChoice = {
  /** The label the person gave it. It is also what a sign-in names: labels
   * are unique on a computer, and the product keeps a profile's identity
   * out of everything it prints. */
  name: string;
  /** The profile the product has selected. */
  active: boolean;
};

export type ProfileList = {
  profiles: ProfileChoice[];
  /** False when the product could not read its profiles coherently: an
   * empty list is then not proof that there are none. */
  complete: boolean;
};

export type ProfileDeleteReview = {
  name: string;
  profileId: string;
  digest: string;
};

/**
 * sign_in_submit and profile_create name a profile in the
 * `x-cadrumo-profile` header: its label as UTF-8, percent-encoded, since a
 * header carries no other text. sign_in_submit may leave it out, and then
 * signs in to the profile the product has selected. profile_create uses a
 * raw UTF-8 password body, as sign_in_submit does.
 */
export type ProfileCreateResult =
  { kind: "created"; name: string } | ({ kind: "refused" } & SignInRefusal);

/**
 * profile_password_change takes a raw UTF-8 body: one JSON object with
 * `current_passphrase`, `new_passphrase` and `new_passphrase_confirmation`,
 * which the host hands to the product's command line and keeps nowhere.
 * `unknown`: the change was submitted and its outcome was not observed, so
 * the old password may or may not still sign in.
 */
export type PasswordChangeResult =
  | { kind: "changed" }
  | ({ kind: "refused" } & SignInRefusal)
  | { kind: "unknown" };

// ---------------------------------------------------------------------------
// Component setup (desktop_setup_*)
// ---------------------------------------------------------------------------
//
// The software Cadrumo needs on this computer -- the browser and the local AI
// (its program and every model it runs, as one item) -- read and set up
// through the held person session. The profile's Google account travels in
// the same snapshot because it rides the same session, but it is not setup:
// it is the profile's own sign-in, read and changed on its own. The host
// pushes a fresh `DesktopSetup` on the observe channel whenever an observed
// setup, check or Google act changes; nothing polls. Every closed value below
// is for choosing what to show; the words to show are the `name`, `sentence`,
// `note` and `action_label` fields, already in the profile's language. Never
// render a closed value itself.

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

export type SetupStaleReason =
  "older_revision" | "different_model_version" | "program_too_old";

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

/** The one button a row offers; its words are the row's `action_label`. */
export type SetupRecovery =
  "set_up" | "update" | "try_again" | "resume" | "check_again";

export type SetupCheckMode = "quick" | "full";

/** Why the local AI's plan entry is worth telling the person about. */
export type SetupAdvisory =
  | "licence_commercial_use_barred"
  | "licence_unverified"
  | "override_not_in_catalogue"
  | "override_below_context_floor"
  | "fit_exceeds_measured_headroom"
  | "fit_unverified";

export type SetupStep =
  "plan" | "preflight" | "download" | "install" | "verify" | "cleanup";

/** One item's derived state and its plain wording. */
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
  /** The item's plain name, such as "Local AI". */
  name: string;
  /** One sentence stating the state and its reason. */
  sentence: string;
  /** For example "downloaded, not loaded yet"; null when there is none. */
  note: string | null;
  /** The button's words for `recovery`; null exactly when it is null. */
  action_label: string | null;
};

/** A status read or a full check this window started. A settled check has
 * already replaced `rows`; a failed one leaves the earlier rows. */
export type SetupCheck = {
  operation_id: string;
  kind: "status_quick" | "status_full" | "verify";
  stage: "running" | "done" | "failed";
};

/** One part of the local AI's plan: its program, or the model one role
 * reads with. A part sharing an earlier part's download has size 0. */
export type SetupPlanPart = {
  part: string;
  name: string;
  /** Null when the size is not known before the download starts. */
  download_bytes: number | null;
};

/** One entry of the plan a person approves: what, how large, from where and
 * where it is stored. Shown, never sent back. */
export type SetupPlanEntry = {
  item: SetupItemId;
  name: string;
  /** Null when the size is not known before the download starts. */
  download_bytes: number | null;
  source_hosts: string[];
  /** The folder it goes into; null when only an outside program installs. */
  destination: string | null;
  installs_outside_program: boolean;
  /** Another entry of this plan that downloads the same files. */
  shares_download_with: SetupItemId | null;
  /** A model's licence notice, such as a non-commercial use limit, in the
   * profile's language; null when there is none. Approving the plan
   * approves it too. */
  licence_notice: string | null;
  /** Empty except on the local AI's entry; approving the plan approves
   * them too. `licence_notice` is present exactly when one is
   * "licence_commercial_use_barred". */
  advisories: SetupAdvisory[];
  /** The local AI's parts in the order setup carries them out; empty for
   * any other item. */
  parts: SetupPlanPart[];
};

/** The plan awaiting approval. `plan_digest` is what an answer binds. */
export type SetupReview = {
  plan_digest: string;
  expires_at: string | null;
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
  /** "Trying again in N seconds (attempt M)", in the profile's language. */
  sentence: string;
};

export type SetupItemResult = {
  changed: boolean;
  failure: SetupFailureCategory | null;
  /** The failure's sentence; null when the item ended usable. */
  sentence: string | null;
  transferred_bytes: number;
};

/** One planned item while setup runs: its current step, byte progress and
 * last retry notice, then its result once setup settles. */
export type SetupItemProgress = {
  item: SetupItemId;
  name: string;
  step: SetupStep | null;
  /** Both null while the size is unknown: show an indeterminate bar. */
  completed: number | null;
  total: number | null;
  retry: SetupRetry | null;
  result: SetupItemResult | null;
};

export type SetupOutcome =
  | "completed"
  | "nothing_to_do"
  | "rejected"
  | "plan_changed"
  | "not_enough_space"
  | "interrupted"
  | "cancelled"
  /** The setup ended without a result of its own; see `failure_sentence`. */
  | "failed";

/** The setup this window started or joined. */
export type SetupRun = {
  operation_id: string;
  stage: "planning" | "review" | "running" | "settled";
  /** Present exactly while `stage` is "review". */
  review: SetupReview | null;
  items: SetupItemProgress[];
  /** Whether Cancel can be offered now. */
  cancellable: boolean;
  cancel_requested: boolean;
  /** Present exactly once `stage` is "settled". */
  outcome: SetupOutcome | null;
  /** Present when `outcome` is "failed". */
  failure_sentence: string | null;
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
  failure: SetupFailureCategory | null;
  /** The failure's sentence; present exactly when `stage` is "failed". */
  sentence: string | null;
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
  setup: SetupRun | null;
  google: GoogleAccount;
  /** The redacted report "Copy details" puts on the clipboard. */
  details: string;
};

/** What the observe channel carries and every setup command answers.
 * `revision` grows with every change; `snapshot` is present exactly when
 * `state` is "ready", which needs a signed-in profile and its runtime. */
export type DesktopSetup = {
  revision: number;
  state: "signed_out" | "unavailable" | "ready";
  snapshot: SetupSnapshot | null;
};

/** Why a setup command was refused; a host failure rejects as `HostFailure`. */
export type SetupRefusalCode =
  /** No profile is signed in. */
  | "not_signed_in"
  /** Another setup, started elsewhere, is running. */
  | "busy"
  /** The plan changed since it was shown; show the new one. */
  | "plan_changed"
  /** No plan of that setup is awaiting an answer, or it is not this window's. */
  | "not_pending"
  /** The setup cannot be cancelled now. */
  | "not_cancellable"
  /** The runtime could not carry the request. */
  | "unavailable";

export type SetupRefusal = { code: SetupRefusalCode };

export type StartupPhase = "environment" | "runtime" | "workspace";
export type StartupProgress = {
  phase: StartupPhase;
  locale: string | null;
  failure: HostFailure | null;
};

export interface HostCommands {
  user_profile_read: {
    args: { language: string };
    result: import("../shell/userProfile").UserProfile;
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
      outputLanguage: import("../shell/modeloContract").OutputLanguage;
    }>;
    result: import("../shell/modeloContract").ModeloDeclarationsListProjectionV1;
  };
  /** One declaration's form, with its admitted edit baseline or refusal. */
  modelo_form: {
    args: Authorized<{
      workUnitId: string;
      outputLanguage: import("../shell/modeloContract").OutputLanguage;
    }>;
    result: import("../shell/modeloContract").ModeloWorkbenchFormProjectionV1;
  };
  modelo_casilla_help: {
    args: Authorized<{
      workUnitId: string;
      casillaId: string;
      registryRevisionId: string;
      calculationRevisionId: string | null;
      outputLanguage: import("../shell/modeloContract").OutputLanguage;
    }>;
    result: import("../shell/modeloContract").ModeloCasillaHelpProjectionV1;
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
   * `modeloEditBody`, at most `MODELO_EDIT_BODY_LIMIT`. */
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
  /** Shows register view `view` in the person's own TUI on the profile
   * signed in here. Refuses `invalid_arguments` for a view the navigation
   * projection does not give the TUI, or a parameter it does not declare
   * with a value of its kind. */
  desktop_present_view: {
    args: Authorized<{
      view: string;
      params: Readonly<Record<string, string>>;
    }>;
    result: PresentationOutcome;
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
  /** Plans setup of `items`, or of every item not ready when null; the plan
   * then awaits an answer in `setup.review`. `model` picks one catalogue
   * model for every role of the local AI. A setup already running is joined.
   * `resume` is the person's Resume click after an interruption: when the
   * new plan is exactly the one approved before, it is approved again
   * without a second review; any other plan awaits an answer as usual. */
  desktop_setup_start: {
    args: Authorized<{
      items: SetupItemId[] | null;
      model: string | null;
      resume: boolean;
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
   * Shows a native popup and resolves when it closes. Refuses
   * `session_unavailable` while another popup is open, `unsupported_platform`
   * on every platform but Windows, and `invalid_arguments` for a malformed
   * request.
   */
  shell_context_menu: {
    args: Authorized<ContextMenuRequest>;
    result: ContextMenuResult;
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
  /** cadrumo-agent's catalog, unchanged and unfiltered. */
  agent_provider_catalog: { args: Authorized; result: AgentProviderCatalog };
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
    }>;
    result: AgentUploadPick[];
  };
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
      method: "browser" | "device";
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
}

/** Native presentation only; no profile or runtime authority. */
export type WindowPresentation = { maximized: boolean; fullscreen: boolean };
export type WindowAction =
  | "minimize"
  | "toggle_maximize"
  | "close"
  | "drag"
  | "focus"
  /** The page's answers to a close it was asked about. */
  | "close_now"
  | "keep_open";

/**
 * What became of a TUI view asked for. `delivered` counts the person's
 * signed-in TUIs on the profile that were passed it; none is zero. A view is
 * only where to look, never access to anything.
 */
export type PresentationOutcome =
  { outcome: "presented"; delivered: number } | { outcome: "signed_out" };

export type HostCommand = keyof HostCommands;
export type HostArguments<C extends HostCommand> = HostCommands[C]["args"];
export type HostResult<C extends HostCommand> = HostCommands[C]["result"];

// ---------------------------------------------------------------------------
// Documentation bridge
// ---------------------------------------------------------------------------

/**
 * Every bridge message is a `window.postMessage` envelope addressed to the
 * peer's exact origin. Each side reads a message only when its `source` is the
 * peer window and its `origin` is the peer origin. An unknown `type` is
 * ignored; another `version` or a malformed known type is refused. The
 * envelope never carries the launch token.
 */
export type BridgeEnvelope<Type extends string> = {
  channel: "cadrumo-desktop";
  version: 1;
  type: Type;
};

export type DocsTheme = "auto" | "light" | "dark";

/**
 * Optional page bridge capabilities a page announces in `ready`. Send a
 * message that needs one only when the page lists it in `ready.features`.
 */
export type BridgeFeature =
  "search" | "navigate" | "home" | "appearance" | (string & {});

export type DocsLink = {
  /** Absolute URL. */
  href: string;
  /** True when the link leaves the documentation origin. */
  external: boolean;
};

/**
 * Documentation result kinds from the docs search controller. Open:
 * the index also carries `legal` records, and a navigation title with no
 * kind of its own arrives as `page`.
 */
export type DocsResultKind =
  "concept" | "cli" | "casilla" | "page" | (string & {});

/**
 * One documentation search result. Results arrive in the docs search
 * controller's own ranking: term, casilla and command cards above pages.
 */
export type DocsSearchResult = {
  kind: DocsResultKind;
  title: string;
  /** An absolute documentation-origin URL; the page never sends another origin. */
  url: string;
  /** Plain text, never HTML; empty when the result has no excerpt. */
  excerpt: string;
  /**
   * Match ranges into `excerpt` as sorted, non-overlapping `[start, end)`
   * offsets in UTF-16 code units, the indices `String.prototype.slice` takes.
   */
  ranges: Array<readonly [start: number, end: number]>;
  /**
   * The controller's localized category line, such as
   * `Casilla · Modelo 200 · 00562`; empty when it has none. Every page that
   * answers `search` sends it.
   */
  crumb?: string;
};

// Documentation page to shell.

export type DocsReady = BridgeEnvelope<"ready"> & {
  url: string;
  title: string;
  lang: string;
  theme: DocsTheme;
  /**
   * Absent on pages that predate the optional capabilities; enable a
   * feature only when listed.
   */
  features?: BridgeFeature[];
};

export type DocsLocation = BridgeEnvelope<"location"> & {
  url: string;
  title: string;
};

export type DocsThemeReport = BridgeEnvelope<"theme"> & { theme: DocsTheme };

/** A relayed shell chord; `id` is the chord id the shell sent in `keymap`. */
export type DocsShortcut = BridgeEnvelope<"shortcut"> & { id: string };

/**
 * A link leaving the documentation origin. Act on it only while
 * `navigator.userActivation.isActive`, under a rate limit, and only through
 * `open_external`.
 */
export type DocsOpenExternal = BridgeEnvelope<"open-external"> & {
  url: string;
};

/** Coordinates are in the frame's viewport CSS pixels, whatever the zoom. */
export type DocsContextMenu = BridgeEnvelope<"context-menu"> & {
  x: number;
  y: number;
  /** At most 65,536 characters. */
  selection: string;
  link: DocsLink | null;
  /**
   * False when the keyboard opened the menu (Shift+F10 or the menu key),
   * true for a pointer. Absent on pages that predate keyboard menus; read
   * `pointer !== false` as pointer-opened.
   */
  pointer?: boolean;
};

/**
 * The answer to a `search` request with the same `id`; sent only by a page
 * that lists `search` in `ready.features`.
 */
export type DocsSearchResults = BridgeEnvelope<"search-results"> & {
  id: string;
  results: DocsSearchResult[];
};

export type DocsToShell =
  | (BridgeEnvelope<"language-change"> & { language: string })
  | DocsReady
  | DocsLocation
  | DocsThemeReport
  | DocsShortcut
  | DocsOpenExternal
  | DocsContextMenu
  | DocsSearchResults;

// Shell to documentation page.

/** Matched on `KeyboardEvent.code`; an omitted modifier means not pressed. */
export type BridgeChord = {
  /** At most 64 characters. */
  id: string;
  /** A `KeyboardEvent.code`, at most 32 characters. */
  code: string;
  ctrlKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  metaKey?: boolean;
};

/** Replaces the page's chord list; at most 64 chords. */
export type ShellKeymap = BridgeEnvelope<"keymap"> & { chords: BridgeChord[] };

export type ShellCommand = BridgeEnvelope<"command"> &
  (
    | { name: "back" }
    | { name: "forward" }
    | { name: "open-search" }
    /**
     * An absolute URL on the documentation origin, at most 4,096 characters;
     * anything else is refused. Optional; send only when the page lists
     * `navigate` in `ready.features`.
     */
    | { name: "navigate"; url: string }
    /**
     * The root of the language the shown page belongs to: the target of the
     * page's own brand link, which is the docs manifest's entry for that
     * language. Optional; send only when the page lists `home` in
     * `ready.features`.
     */
    | { name: "home" }
  );

/** Documentation zoom, 0.5 to 2.0; 1 restores the page's own size. */
export type ShellZoom = BridgeEnvelope<"zoom"> & { factor: number };

/**
 * A bounded search, answered by one `search-results` with the same `id`. A
 * refused request is never answered. A blank query is answered with no
 * results. Optional; send only when the page lists `search` in
 * `ready.features`.
 */
export type ShellSearch = BridgeEnvelope<"search"> & {
  /** At most 64 characters; at most one request in flight per `id`. */
  id: string;
  /** At most 256 characters. At most eight searches are in flight at once. */
  query: string;
  /** An integer from 1 to 50. */
  limit: number;
};

/**
 * Applied the way Furo's own toggle applies a theme, and persisted the same
 * way for later pages; answered by one `theme` report. `auto` hands the
 * choice back to the page's toggle. Optional; send only when the page lists
 * `appearance` in `ready.features`.
 */
export type ShellAppearance = BridgeEnvelope<"appearance"> & {
  theme: DocsTheme;
};

export type ShellToDocs =
  ShellKeymap | ShellCommand | ShellZoom | ShellSearch | ShellAppearance;

export type BridgeMessage = DocsToShell | ShellToDocs;
