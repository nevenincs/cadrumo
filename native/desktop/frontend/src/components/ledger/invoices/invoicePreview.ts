// The backend's answer for the draft on the page. A draft is sent as typed on
// a short pause or a committed field, one request at a time, and the latest
// wins. An answer belongs to the exact request it was asked with: the window
// cannot derive `input_digest` without copying its canonical form, so it keeps
// the digest beside the request that earned it and compares the requests. The
// last answer stays on show while a newer one is awaited, and is never taken
// for the newer draft's. A failed read leaves no figure and no rate behind.

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type {
  InvoicePreviewRequest,
  InvoicePreviewResult,
  LedgerPort,
} from "../../../shell/ledger";
import { readAnswer } from "../../../shell/ledgerWindow";

export type PreviewReply =
  { kind: "answer"; result: InvoicePreviewResult } | { kind: "failed" };

export type PreviewView = {
  /** The last answer, for this draft or an earlier one, to draw figures from. */
  shown: InvoicePreviewResult | null;
  /** The answer to the draft as it stands now, the only one to act on. */
  current: InvoicePreviewResult | null;
  /** The digest of `current`. */
  digest: string | null;
  /** A newer answer is awaited. */
  updating: boolean;
  /** The last read answered nothing. It is a read: it failed, nothing is
   * unknown. */
  failed: boolean;
};

/** How long typing rests before the draft is asked about. */
const PAUSE_MS = 250;

const IDLE: PreviewView = {
  shown: null,
  current: null,
  digest: null,
  updating: false,
  failed: false,
};

export class InvoicePreviewSession {
  private view = IDLE;
  private readonly listeners = new Set<() => void>();
  private wanted: { key: string; request: InvoicePreviewRequest } | null = null;
  private answer: InvoicePreviewResult | null = null;
  private answeredKey: string | null = null;
  private failedKey: string | null = null;
  private sending = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private running = true;

  constructor(
    private readonly ask: (
      request: InvoicePreviewRequest,
    ) => Promise<PreviewReply>,
    private readonly pauseMs = PAUSE_MS,
  ) {}

  readonly subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  readonly snapshot = () => this.view;

  /** The draft as it stands now: asked about after a pause, unless answered. */
  want(request: InvoicePreviewRequest): void {
    const key = JSON.stringify(request);
    this.wanted = { key, request };
    this.clearTimer();
    this.publish();
    if (this.settledFor(key)) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.send();
    }, this.pauseMs);
  }

  /** A field was committed: the pause is over. */
  commit(): void {
    if (this.timer === null) return;
    this.clearTimer();
    this.send();
  }

  /** Asks again about a draft whose read failed. */
  retry(): void {
    this.failedKey = null;
    this.clearTimer();
    this.publish();
    this.send();
  }

  start(): void {
    this.running = true;
  }
  stop(): void {
    this.running = false;
    this.clearTimer();
  }

  private settledFor(key: string): boolean {
    return key === this.answeredKey || key === this.failedKey;
  }

  private clearTimer(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }

  private send(): void {
    const asked = this.wanted;
    if (!this.running || this.sending || !asked || this.settledFor(asked.key))
      return;
    this.sending = true;
    void this.ask(asked.request)
      .catch((): PreviewReply => ({ kind: "failed" }))
      .then((reply) => this.settle(asked.key, reply));
  }

  private settle(key: string, reply: PreviewReply): void {
    this.sending = false;
    if (!this.running) return;
    // Only the latest draft's reply counts; a stale one says nothing at all,
    // and the draft that overtook it is asked about now unless still pausing.
    if (key !== this.wanted?.key) {
      if (this.timer === null) this.send();
      return;
    }
    this.answer = reply.kind === "answer" ? reply.result : null;
    this.answeredKey = reply.kind === "answer" ? key : null;
    this.failedKey = reply.kind === "answer" ? null : key;
    this.publish();
  }

  private publish(): void {
    const key = this.wanted?.key ?? null;
    const answered = key !== null && key === this.answeredKey;
    const failed = key !== null && key === this.failedKey;
    this.view = {
      shown: this.answer,
      current: answered ? this.answer : null,
      digest: answered ? (this.answer?.input_digest ?? null) : null,
      updating: key !== null && !answered && !failed,
      failed,
    };
    this.listeners.forEach((listener) => listener());
  }
}

/** Asks the ledger once. Every way of not answering is the same failure. */
export async function askPreview(
  port: LedgerPort,
  request: InvoicePreviewRequest,
): Promise<PreviewReply> {
  try {
    const answer = readAnswer(
      await port.submit("ledger.invoice.preview", request),
    );
    return answer.kind === "answer"
      ? { kind: "answer", result: answer.result }
      : { kind: "failed" };
  } catch {
    return { kind: "failed" };
  }
}

/** The preview of `request`, kept current while the editor is open. */
export function useInvoicePreview(
  port: LedgerPort,
  request: InvoicePreviewRequest,
) {
  const [session] = useState(
    () => new InvoicePreviewSession((asked) => askPreview(port, asked)),
  );
  const view = useSyncExternalStore(session.subscribe, session.snapshot);
  const key = JSON.stringify(request);
  useEffect(() => {
    session.start();
    return () => session.stop();
  }, [session]);
  useEffect(() => {
    session.want(JSON.parse(key) as InvoicePreviewRequest);
  }, [session, key]);
  return useMemo(
    () => ({
      ...view,
      commit: () => session.commit(),
      retry: () => session.retry(),
    }),
    [session, view],
  );
}
