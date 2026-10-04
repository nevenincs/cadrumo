import { Channel, invoke } from "@tauri-apps/api/core";
import type { HostFailure, ShellToken } from "../ipc/contract";
import type { TerminalEvent, TerminalKind, TerminalSession } from "./host";

// One channel per session carries tagged frames in order: a tag byte, then
// the payload. Data frames are the only bytes acknowledgements count.
const TAG_DATA = 0;
const TAG_STARTED = 1;
const TAG_EXITED = 2;
const TAG_FAILED = 3;

/** Bytes per write call; the host's JSON fallback accepts at most 64 KiB. */
const WRITE_CHUNK = 16384;
/** Acknowledge after this many rendered bytes, well under the 512 KiB pause. */
const ACK_EVERY = 32768;
const ACK_IDLE_MS = 50;
const RETRY_FIRST_MS = 10;
const RETRY_MAX_MS = 250;

const clampSize = (value: number) =>
  Math.max(2, Math.min(1000, Math.round(value)));
const decoder = new TextDecoder();

function frameBytes(message: unknown): Uint8Array | null {
  if (message instanceof ArrayBuffer) return new Uint8Array(message);
  if (ArrayBuffer.isView(message))
    return new Uint8Array(
      message.buffer,
      message.byteOffset,
      message.byteLength,
    );
  if (Array.isArray(message)) return Uint8Array.from(message as number[]);
  return null;
}

function readJson(payload: Uint8Array): Record<string, unknown> {
  try {
    const value: unknown = JSON.parse(decoder.decode(payload));
    return value && typeof value === "object"
      ? (value as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

function isQueueFull(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    (error as Partial<HostFailure>).code === "queue_full"
  );
}

const pause = (ms: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, ms));

export async function openTauriTerminal(
  token: ShellToken,
  kind: TerminalKind,
  size: { cols: number; rows: number },
  listener: (event: TerminalEvent) => void,
): Promise<TerminalSession> {
  let session: number | null = null;
  let rendered = 0;
  let acknowledged = 0;
  let ackTimer = 0;

  // Acknowledge the cumulative offset of rendered data; never more often than
  // needed, never so rarely that the host pauses a live session.
  const flushAck = () => {
    window.clearTimeout(ackTimer);
    ackTimer = 0;
    if (session === null || rendered === acknowledged) return;
    acknowledged = rendered;
    void invoke("terminal_ack", { token, session, offset: rendered }).catch(
      () => undefined,
    );
  };

  const output = new Channel<unknown>();
  output.onmessage = (message) => {
    const frame = frameBytes(message);
    if (!frame || frame.length === 0) return;
    const payload = frame.subarray(1);
    switch (frame[0]) {
      case TAG_DATA:
        listener({ type: "data", bytes: payload });
        break;
      case TAG_STARTED:
        listener({ type: "started" });
        break;
      case TAG_EXITED: {
        const code = readJson(payload).code;
        flushAck();
        listener({
          type: "exited",
          code: typeof code === "number" ? code : null,
        });
        break;
      }
      case TAG_FAILED: {
        const error = readJson(payload).error as
          Partial<HostFailure> | undefined;
        // The host's message is fixed English; the shell names the typed code.
        listener({
          type: "failed",
          message: typeof error?.code === "string" ? error.code : "unknown",
        });
        break;
      }
      default:
    }
  };

  const opened = await invoke<{ session: number }>("terminal_open", {
    token,
    kind,
    cols: clampSize(size.cols),
    rows: clampSize(size.rows),
    output,
  });
  session = opened.session;
  const id = opened.session;
  const headers = { "x-cadrumo-token": token, "x-cadrumo-session": String(id) };

  const writeChunk = async (chunk: Uint8Array) => {
    // A full queue is backpressure, not loss: wait and send the same bytes.
    for (
      let delay = RETRY_FIRST_MS;
      ;
      delay = Math.min(RETRY_MAX_MS, delay * 2)
    ) {
      try {
        await invoke("terminal_write", chunk, { headers });
        return;
      } catch (error) {
        if (!isQueueFull(error)) throw error;
        await pause(delay);
      }
    }
  };

  return {
    async write(bytes) {
      for (let offset = 0; offset < bytes.length; offset += WRITE_CHUNK) {
        await writeChunk(bytes.subarray(offset, offset + WRITE_CHUNK));
      }
    },
    ack(bytes) {
      rendered += bytes;
      if (rendered - acknowledged >= ACK_EVERY) flushAck();
      else if (!ackTimer) ackTimer = window.setTimeout(flushAck, ACK_IDLE_MS);
    },
    async resize(cols, rows) {
      await invoke("terminal_resize", {
        token,
        session: id,
        cols: clampSize(cols),
        rows: clampSize(rows),
      });
    },
    async close() {
      window.clearTimeout(ackTimer);
      await invoke("terminal_close", { token, session: id });
    },
  };
}
