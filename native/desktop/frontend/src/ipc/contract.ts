// The desktop shell's published IPC contract: the app commands the Rust host
// registers, the frames its channels carry, and the postMessage bridge between
// the shell document and the documentation frame.
//
// Types only. This module emits no runtime code; field names and casing follow
// the host's serde output exactly. Where the host side is still being built,
// the comment on the type names the Step that implements it.

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
  | "lock_poisoned"
  | "log_unavailable"
  | "desktop_unavailable"
  | "webview_failed"
  | "unsupported_platform"
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
};

/** `ProcessRole` in `native/application/src/process/status.rs`. */
export type ProcessRole = "environment" | "cli" | "tui" | "repl" | "console";

// ---------------------------------------------------------------------------
// desktop_environment (S07)
// ---------------------------------------------------------------------------

export type DocsLanguage = {
  /** Language code, for example `en`, `es`, `ca`, `hu`. */
  code: string;
  /** The language's entry from the docs manifest. Use it as given. */
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

/** Open enumeration: `"python"` and `"host"` today; render unknown sources. */
export type LogSource = "python" | "host" | (string & {});

export type LogProcess = { role: ProcessRole; pid: number };

export type LogRecord = {
  /** Increases by one per record across the host's ring. */
  seq: number;
  source: LogSource;
  /** The timestamp as written; empty when the line carried none. */
  timestamp: string;
  /** `timestamp` parsed to Unix milliseconds, or null when unparseable. */
  timestampMs: number | null;
  level: LogLevel | null;
  logger: string | null;
  message: string;
  /** Continuation lines, such as a traceback. */
  detail: string | null;
  /** The host process an event concerns; null for Python file records. */
  process: LogProcess | null;
};

export type LogSourceKind = "available" | "missing" | "unreadable";

/** "missing" and "unreadable" are distinct from an empty list of records. */
export type LogSourceState = {
  kind: LogSourceKind;
  /** The log file the state describes. */
  detail: string;
  /** Why the file could not be read; set only for `unreadable`. */
  failure: HostFailure | null;
};

/**
 * One delivery on a subscription's channel; at most ten per second. The first
 * batch carries up to 5,000 records of backlog from a 10,000-record ring.
 */
export type LogBatch = {
  records: LogRecord[];
  /** Records this subscription lost to ring overflow since its previous batch. */
  dropped: number;
  state: LogSourceState;
};

export type LogSubscription = {
  subscription: number;
  state: LogSourceState;
};

// ---------------------------------------------------------------------------
// Shell services (S07)
// ---------------------------------------------------------------------------

export type ClipboardText = { text: string };

export type ContextMenuAction = {
  /** Unique within one menu; the host namespaces it internally. */
  id: string;
  label: string;
  enabled: boolean;
  /** Display-only accelerator text shown beside the label; binds nothing. */
  shortcut?: string;
};

export type ContextMenuSeparator = { separator: true };

export type ContextMenuItem = ContextMenuAction | ContextMenuSeparator;

export type ContextMenuRequest = {
  items: ContextMenuItem[];
  /**
   * Logical position in shell CSS pixels: for a documentation menu, the
   * iframe rect plus its border plus the relayed client coordinates, with no
   * device-pixel scaling. Omit both for a pointer-opened menu, which opens at
   * the cursor.
   */
  x?: number;
  y?: number;
};

/** Resolves when the native menu closes; `null` when it was dismissed. */
export type ContextMenuResult = { chosen: string | null };

// ---------------------------------------------------------------------------
// Terminals (S04)
// ---------------------------------------------------------------------------

// ==== BEGIN S04 TERMINAL CONTRACT (pending) =================================
// terminal_open, the tagged frame encoding on the single per-session channel,
// terminal_write, terminal_ack, terminal_resize, terminal_close and
// diagnostics_snapshot are defined here once S04 fixes them. Until then this
// block declares nothing usable, so no consumer can depend on a guessed shape.
export type TerminalContractPending = never;
// ==== END S04 TERMINAL CONTRACT =============================================

// ---------------------------------------------------------------------------
// Command table
// ---------------------------------------------------------------------------

/**
 * Every app command with JSON arguments: its arguments (all carrying the
 * token) and the value it resolves with. A refused call rejects with a
 * `HostFailure`. Commands that return nothing resolve with `null`.
 */
export interface HostCommands {
  desktop_environment: {
    args: Authorized;
    result: DesktopEnvironment;
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
  /** Accepts only `https:` and `mailto:` URLs; refuses every other scheme. */
  open_external: {
    args: Authorized<{ url: string }>;
    result: null;
  };
  shell_clipboard_read: {
    args: Authorized;
    result: ClipboardText;
  };
  /** `text` is at most 1 MiB. */
  shell_clipboard_write: {
    args: Authorized<ClipboardText>;
    result: null;
  };
  /** Refuses a second menu while one is open. */
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

/** Page bridge capabilities a page announces in `ready` (S14). */
export type BridgeFeature =
  "search" | "navigate" | "home" | "appearance" | (string & {});

export type DocsLink = {
  /** Absolute URL. */
  href: string;
  /** True when the link leaves the documentation origin. */
  external: boolean;
};

/** Documentation result kinds from the docs search controller (S14). */
export type DocsResultKind =
  "concept" | "cli" | "casilla" | "page" | (string & {});

/** One documentation search result (S14). */
export type DocsSearchResult = {
  kind: DocsResultKind;
  title: string;
  /** A documentation-origin URL; the page never sends another origin. */
  url: string;
  /** Plain text, never HTML. */
  excerpt: string;
  /** Match ranges into `excerpt` as `[start, end)` character offsets. */
  ranges: Array<readonly [start: number, end: number]>;
};

// Documentation page to shell.

export type DocsReady = BridgeEnvelope<"ready"> & {
  url: string;
  title: string;
  lang: string;
  theme: DocsTheme;
  /** Absent on pages built before S14; enable a feature only when listed. */
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
};

/** The answer to a `search` request with the same `id` (S14). */
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
    /** Refused for a URL outside the documentation origin (S14). */
    | { name: "navigate"; url: string }
    /** The active language's manifest entry (S14). */
    | { name: "home" }
  );

/** Documentation zoom, 0.5 to 2.0; 1 restores the page's own size. */
export type ShellZoom = BridgeEnvelope<"zoom"> & { factor: number };

/** A bounded query; at most one request in flight per `id` (S14). */
export type ShellSearch = BridgeEnvelope<"search"> & {
  id: string;
  query: string;
  limit: number;
};

/** Applied the way Furo's own toggle applies a theme; `auto` hands the choice back (S14). */
export type ShellAppearance = BridgeEnvelope<"appearance"> & {
  theme: DocsTheme;
};

export type ShellToDocs =
  ShellKeymap | ShellCommand | ShellZoom | ShellSearch | ShellAppearance;

export type BridgeMessage = DocsToShell | ShellToDocs;
