// The terminal sessions' wire shapes: the frames their channels carry, with
// the frame tags as constants, and the bodies of the commands that open, size,
// write to and close one. Field names and casing follow the host's serde
// output exactly.

import type {
  HostFailure,
  SessionHeader,
  ShellToken,
  TokenHeader,
} from "./contract";

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
