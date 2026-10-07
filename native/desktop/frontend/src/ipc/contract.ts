// The desktop shell's published IPC contract: the app commands the Rust host
// registers, the frames its channels carry, and the postMessage bridge between
// the shell document and the documentation frame.
//
// Types, plus the terminal frame tags as constants; nothing else here runs.
// Field names and casing follow the host's serde output exactly.

import type { Channel } from "@tauri-apps/api/core";

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
  | "shutdown";

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

export type DesktopEnvironment = {
  /** The output language Settings resolved for this profile. */
  outputLanguage: string;
  docs: {
    /** The documentation origin, computed by the host for this platform. */
    origin: string;
    languages: DocsLanguage[];
  };
};

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

/** Independent file availability; host events are read from memory. */
export type LogSourceStates = {
  python: LogSourceState;
  manager: LogSourceState;
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
  | "failure"
  | "host_stopped";

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
  source: "desktop" | "manager";
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
export type SignInRefusal = { code: string; retryAfterSeconds: number | null };

/** Presence only: reading this never resumes or extends a sign-in. */
export type SignInStatus = {
  supported: boolean;
  state: "present" | "absent" | "unknown";
  active_profile: string | null;
  runtimeAvailable: boolean;
  refusal: SignInRefusal | null;
};

/** sign_in_submit uses a raw UTF-8 password body and x-cadrumo-token header. */
export type SignInResult =
  { kind: "signed-in" } | ({ kind: "refused" } & SignInRefusal);

export type SignOutResult = {
  remainingAccess: {
    automationEnabled: boolean | null;
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

/**
 * sign_in_submit and profile_create name a profile in the
 * `x-cadrumo-profile` header: its label as UTF-8, percent-encoded, since a
 * header carries no other text. sign_in_submit may leave it out, and then
 * signs in to the profile the product has selected. profile_create uses a
 * raw UTF-8 password body, as sign_in_submit does.
 */
export type ProfileCreateResult =
  { kind: "created"; name: string } | ({ kind: "refused" } & SignInRefusal);

export interface HostCommands {
  manager_start: {
    args: Authorized;
    result: "dispatched" | "unmanaged" | "unsupported";
  };
  sign_in_status: { args: Authorized; result: SignInStatus };
  sign_out: { args: Authorized; result: SignOutResult };
  /** Needs no password, session or runtime, and changes nothing. */
  profile_list: { args: Authorized; result: ProfileList };
  desktop_environment: {
    args: Authorized;
    result: DesktopEnvironment;
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
}

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
