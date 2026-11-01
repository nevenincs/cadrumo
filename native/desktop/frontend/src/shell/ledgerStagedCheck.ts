// The backend's answer for what is staged. Which write takes a cell, what a
// row's staged state would refuse and what would give it a new id are the
// writers' rules, so the page asks `ledger.staged.check` and holds no copy.
// An answer belongs to the exact request it was asked with; the latest wins, a
// stale reply says nothing, and with no answer there is no plan to act on: the
// staged work stays and the action waits.

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type {
  LedgerPort,
  LedgerRow,
  LedgerStagedCell,
  LedgerStagedCheckRequest,
  LedgerStagedCheckResult,
  LedgerStagedDraft,
  LedgerStagedRow,
  LedgerStagedRowAnswer,
} from "./ledger";
import { readAnswer } from "./ledgerWindow";
import {
  actionRows,
  STAGE_FIELDS,
  type StagedAction,
  type StagedContent,
  type StagedRowChanges,
} from "./ledgerStage";

/** The answer, found by what was asked about. */
export type StagedCheck = {
  rows: ReadonlyMap<string, LedgerStagedRowAnswer>;
  drafts: ReadonlyMap<
    string,
    readonly LedgerStagedCheckResult["drafts"][number]["blockers"][number][]
  >;
  categories: ReadonlyMap<string, { business: boolean; mixed: boolean }>;
};

export function indexCheck(result: LedgerStagedCheckResult): StagedCheck {
  return {
    rows: new Map(result.rows.map((row) => [row.transaction_id, row])),
    drafts: new Map(result.drafts.map((draft) => [draft.key, draft.blockers])),
    categories: new Map(
      result.categories.map(({ category, business, mixed }) => [
        category,
        { business, mixed },
      ]),
    ),
  };
}

const evidenceStaged = (action: StagedAction, id: string) =>
  (action.kind === "attach" &&
    action.transactionId === id &&
    action.evidenceId !== null) ||
  (action.kind === "attach_file" && action.transactionId === id);

function stagedRow(
  id: string,
  changes: StagedRowChanges | undefined,
  actions: readonly StagedAction[],
): LedgerStagedRow {
  const cells: LedgerStagedCell[] = [];
  for (const field of STAGE_FIELDS) {
    const change = changes?.[field];
    if (change)
      cells.push({
        field,
        value: change.kind === "set" ? change.value : null,
      });
  }
  return {
    transaction_id: id,
    cells,
    evidence_staged: actions.some((action) => evidenceStaged(action, id)),
    m210_staged: actions.some(
      (action) => action.kind === "m210" && actionRows(action).includes(id),
    ),
  };
}

/** What to ask about: every staged row and new movement, and any other
 * movements or categories the page is about to judge. Rows the page no longer
 * holds are left out; they are gone, which the plan says itself. */
export function stagedCheckRequest(
  content: StagedContent,
  rows: ReadonlyMap<string, LedgerRow>,
  also: { ids?: readonly string[]; categories?: readonly string[] } = {},
): LedgerStagedCheckRequest {
  const ids = new Set<string>([
    ...Object.keys(content.rows),
    ...content.actions.flatMap((action) => actionRows(action)),
    ...(also.ids ?? []),
  ]);
  const asked = [...ids].filter((id) => rows.has(id)).sort();
  const drafts: LedgerStagedDraft[] = content.drafts.map((draft) => ({
    key: draft.key,
    fields: Object.entries(draft.fields)
      .filter(([, value]) => typeof value === "string")
      .map(([field, value]) => ({ field, value: value as string }))
      .sort((a, b) => (a.field < b.field ? -1 : 1)),
  }));
  return {
    rows: asked.map((id) => stagedRow(id, content.rows[id], content.actions)),
    drafts,
    categories: [...new Set(also.categories ?? [])].sort(),
  };
}

export type CheckReply =
  { kind: "answer"; result: LedgerStagedCheckResult } | { kind: "failed" };

/** Asks the ledger once. Every way of not answering is the same failure. */
export async function askStagedCheck(
  port: LedgerPort,
  request: LedgerStagedCheckRequest,
): Promise<CheckReply> {
  try {
    const answer = readAnswer(
      await port.submit("ledger.staged.check", request),
    );
    return answer.kind === "answer"
      ? { kind: "answer", result: answer.result }
      : { kind: "failed" };
  } catch {
    return { kind: "failed" };
  }
}

/** One asked question's answer, or null where the ledger gave none. */
export async function checkOnce(
  port: LedgerPort,
  request: LedgerStagedCheckRequest,
): Promise<StagedCheck | null> {
  const reply = await askStagedCheck(port, request);
  return reply.kind === "answer" ? indexCheck(reply.result) : null;
}

export type CheckView = {
  /** The last answer, for this request or an earlier one, to draw from. */
  shown: StagedCheck | null;
  /** The answer to the request as it stands now, the only one to act on. */
  current: StagedCheck | null;
  updating: boolean;
  failed: boolean;
};

const IDLE: CheckView = {
  shown: null,
  current: null,
  updating: false,
  failed: false,
};
/** How long editing rests before what is staged is asked about. */
const PAUSE_MS = 250;
const NOTHING_ASKED = (request: LedgerStagedCheckRequest) =>
  request.rows.length === 0 &&
  request.drafts.length === 0 &&
  request.categories.length === 0;
/** What is known with nothing asked. */
export const NOTHING_CHECKED: StagedCheck = {
  rows: new Map(),
  drafts: new Map(),
  categories: new Map(),
};

export class StagedCheckSession {
  private view = IDLE;
  private readonly listeners = new Set<() => void>();
  private wanted: { key: string; request: LedgerStagedCheckRequest } | null =
    null;
  private answer: StagedCheck | null = null;
  private answeredKey: string | null = null;
  private failedKey: string | null = null;
  private sending = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private running = true;

  constructor(
    private readonly ask: (
      request: LedgerStagedCheckRequest,
    ) => Promise<CheckReply>,
    private readonly pauseMs = PAUSE_MS,
  ) {}

  readonly subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  readonly snapshot = () => this.view;

  want(request: LedgerStagedCheckRequest): void {
    const key = JSON.stringify(request);
    this.wanted = { key, request };
    this.clearTimer();
    if (NOTHING_ASKED(request)) {
      this.answer = NOTHING_CHECKED;
      this.answeredKey = key;
      this.failedKey = null;
      this.publish();
      return;
    }
    this.publish();
    if (key === this.answeredKey || key === this.failedKey) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.send();
    }, this.pauseMs);
  }

  /** Asks again about a request whose read failed. */
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

  private clearTimer(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }

  private send(): void {
    const asked = this.wanted;
    if (
      !this.running ||
      this.sending ||
      !asked ||
      asked.key === this.answeredKey ||
      asked.key === this.failedKey
    )
      return;
    this.sending = true;
    void this.ask(asked.request)
      .catch((): CheckReply => ({ kind: "failed" }))
      .then((reply) => this.settle(asked.key, reply));
  }

  private settle(key: string, reply: CheckReply): void {
    this.sending = false;
    if (!this.running) return;
    // Only the latest request's reply counts; the one that overtook it is
    // asked about now unless still pausing.
    if (key !== this.wanted?.key) {
      if (this.timer === null) this.send();
      return;
    }
    this.answer = reply.kind === "answer" ? indexCheck(reply.result) : null;
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
      updating: key !== null && !answered && !failed,
      failed,
    };
    this.listeners.forEach((listener) => listener());
  }
}

/** The answer for `request`, kept current while the page holds it. */
export function useStagedCheck(
  port: LedgerPort,
  request: LedgerStagedCheckRequest,
) {
  const [session] = useState(
    () => new StagedCheckSession((asked) => askStagedCheck(port, asked)),
  );
  const view = useSyncExternalStore(session.subscribe, session.snapshot);
  const key = JSON.stringify(request);
  useEffect(() => {
    session.start();
    return () => session.stop();
  }, [session]);
  useEffect(() => {
    session.want(JSON.parse(key) as LedgerStagedCheckRequest);
  }, [session, key]);
  return useMemo(
    () => ({ ...view, retry: () => session.retry() }),
    [session, view],
  );
}
