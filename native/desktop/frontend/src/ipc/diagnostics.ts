// What `diagnostics_snapshot` reports of the desktop's processes, helpers and
// webview. Field names and casing follow the host's serde output exactly.

import type {
  HostErrorCode,
  HostFailure,
  LogLevel,
  ProcessRole,
} from "./contract";

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
  | "service_event"
  | "desktop_diagnostic"
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
  /** The terminal session a terminal failure concerns; omitted otherwise. */
  terminalSession?: number;
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
  desktopDiagnostic?: DesktopDiagnostic;
};

export type DesktopDiagnostic = {
  origin: "frontend" | "rust" | "tauri";
  logger: string | null;
  event:
    | "command_rejected"
    | "uncaught_error"
    | "unhandled_rejection"
    | "react_error"
    | "console"
    | "native_log";
  level: LogLevel;
  command: string | null;
  code: HostErrorCode | null;
  dropped: number;
  line: number | null;
  column: number | null;
  /** The backend's closed code beside a relay failure's `code`. */
  reason?: string;
  /** What the record said, without any of its values. */
  summary?: { template: string | null; module: string | null };
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
    | "completed"
    | "interrupted";
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
      webview: "startup" | "main" | "other";
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
      webview: "startup" | "main" | "other";
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
