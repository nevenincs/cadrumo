// The Sede view port: the profile worker's own browser page, streamed to the
// window as images while the person's input travels back. The window holds a
// view only in memory: a frame, an address, a title and a typed key are never
// kept, written or logged, and the window names no address of its own.

import type {
  SedeViewFailure,
  SedeViewFailureCode,
  SedeViewInput,
  SedeViewMessage,
  SedeViewVerb,
} from "../ipc/contract";

/** The panel's size in CSS pixels, and the device pixel ratio. */
export type SedeViewSize = {
  cssWidth: number;
  cssHeight: number;
  scale: number;
};

/** Everything the view says. An image arrives with the bytes it announced,
 * or with none where the host did not send them whole. */
export type SedeViewEvent =
  | Exclude<SedeViewMessage, { kind: "image" }>
  | (Extract<SedeViewMessage, { kind: "image" }> & {
      bytes: ArrayBuffer | null;
    });

/** An open view. A refused call rejects with the host's `{ code }`. */
export type SedeViewSession = {
  /** Forwards one input event of the person. */
  input(event: SedeViewInput): Promise<void>;
  navigate(verb: SedeViewVerb): Promise<void>;
  resize(size: SedeViewSize): Promise<void>;
  /** One for each image message received, drawn or not. */
  credit(): Promise<void>;
  dialog(dialogId: number, accept: boolean, promptText?: string): Promise<void>;
  /** With `save`, the native save dialog asks where the file goes. */
  downloadAnswer(
    transferId: number,
    save: boolean,
  ): Promise<{ saving: boolean }>;
  /** With `choose`, the native open dialog asks which files go to the page. */
  fileChooserAnswer(
    chooserId: number,
    choose: boolean,
  ): Promise<{ supplied: number }>;
  /** Opens the page the host holds in the system browser. The window sends
   * no address. */
  openExternal(): Promise<void>;
  /** The person left: the view publishes its session and ends. */
  close(): Promise<void>;
};

export type SedeViewPort = {
  /** Opens the view at the panel's size. The host refuses `conflict` while
   * the previous view is still publishing its session. */
  open(
    size: SedeViewSize,
    listener: (event: SedeViewEvent) => void,
  ): Promise<SedeViewSession>;
};

const FAILURE_CODES: readonly SedeViewFailureCode[] = [
  "invalid",
  "not_admitted",
  "conflict",
  "unavailable",
  "file_unavailable",
  "refused",
  "unknown",
  "not_signed_in",
];

/** The typed failure of a rejected view call. A rejection that is not the
 * host's own answer never reached it and is `unavailable`. */
export function sedeViewFailure(error: unknown): SedeViewFailure {
  const found = error as { code?: unknown } | null;
  const code = FAILURE_CODES.find((known) => known === found?.code);
  return { code: code ?? "unavailable", operation_id: null };
}

/** The most CSS pixels the host accepts along either side of the panel, and
 * the device pixel ratios it accepts. */
const EXTENT_LIMIT = 4096;
const SCALE_MIN = 0.5;
const SCALE_MAX = 4;

/** The panel's size as the host accepts it, or null while the panel has no
 * room to show anything. */
export function sedeViewSize(
  box: { width: number; height: number },
  ratio: number,
): SedeViewSize | null {
  const cssWidth = Math.min(EXTENT_LIMIT, Math.floor(box.width));
  const cssHeight = Math.min(EXTENT_LIMIT, Math.floor(box.height));
  if (cssWidth < 1 || cssHeight < 1) return null;
  const scale = Number.isFinite(ratio)
    ? Math.min(SCALE_MAX, Math.max(SCALE_MIN, ratio))
    : 1;
  return { cssWidth, cssHeight, scale };
}

type Announced = Extract<SedeViewMessage, { kind: "image" }>;

function rawBytes(delivery: unknown): ArrayBuffer | null {
  if (delivery instanceof ArrayBuffer) return delivery;
  if (ArrayBuffer.isView(delivery))
    return new Uint8Array(
      delivery.buffer,
      delivery.byteOffset,
      delivery.byteLength,
    ).slice().buffer;
  // Where the transport falls back to JSON, raw bytes arrive as numbers.
  if (Array.isArray(delivery))
    return Uint8Array.from(delivery as number[]).buffer;
  return null;
}

function isMessage(delivery: unknown): delivery is SedeViewMessage {
  const found = delivery as { kind?: unknown; view?: unknown } | null;
  return (
    typeof found === "object" &&
    found !== null &&
    typeof found.kind === "string" &&
    typeof found.view === "number"
  );
}

/**
 * Reads a view's channel into its events. The channel carries the host's JSON
 * messages in order and, after each `image` message, one raw message holding
 * that image's JPEG bytes; the two are handed on as one event. The host may
 * send before its answer to the open call arrives, so what comes first waits
 * for `open` to name the view it belongs to. A message of another view is
 * dropped. An image whose bytes did not follow whole is still an event, with
 * no bytes, so that it is credited all the same.
 */
export function sedeViewReader(listener: (event: SedeViewEvent) => void): {
  accept(delivery: unknown): void;
  open(view: number): void;
} {
  let view: number | null = null;
  const early: unknown[] = [];
  let announced: Announced | null = null;

  const handle = (delivery: unknown) => {
    const bytes = rawBytes(delivery);
    if (bytes) {
      const image = announced;
      announced = null;
      // Bytes nothing announced have no image to draw or credit.
      if (!image) return;
      listener({
        ...image,
        bytes: bytes.byteLength === image.byte_length ? bytes : null,
      });
      return;
    }
    if (!isMessage(delivery) || delivery.view !== view) return;
    if (announced) {
      const lost = announced;
      announced = null;
      listener({ ...lost, bytes: null });
    }
    if (delivery.kind === "image") announced = delivery;
    else listener(delivery);
  };

  return {
    accept(delivery) {
      if (view === null) early.push(delivery);
      else handle(delivery);
    },
    open(named) {
      view = named;
      for (const delivery of early.splice(0)) handle(delivery);
    },
  };
}
