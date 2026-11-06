import { ReadSessionScheduler } from "../../../shell/readSessionScheduler";
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
} from "../../../shell/ledgerInvoiceOperations";
import type { LedgerPort } from "../../../shell/ledger";
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

export class InvoicePreviewSession extends ReadSessionScheduler<
  InvoicePreviewRequest,
  string,
  InvoicePreviewResult,
  InvoicePreviewResult,
  PreviewView
> {
  constructor(
    ask: (request: InvoicePreviewRequest) => Promise<PreviewReply>,
    pauseMs = PAUSE_MS,
  ) {
    super({
      ask,
      keyOf: (request) => JSON.stringify(request),
      answer: (result) => result,
      present: (view) => ({
        ...view,
        digest: view.current?.input_digest ?? null,
      }),
      initial: IDLE,
      pauseMs,
    });
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
