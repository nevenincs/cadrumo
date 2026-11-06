import { ReadSessionScheduler } from "./readSessionScheduler";
// The backend's answer for what is staged. Which write takes a cell, what a
// row's staged state would refuse and what would give it a new id are the
// writers' rules, so the page asks `ledger.staged.check` and holds no copy.
// An answer belongs to the exact request it was asked with; the latest wins, a
// stale reply says nothing, and with no answer there is no plan to act on: the
// staged work stays and the action waits.

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type { LedgerPort, LedgerRow } from "./ledger";
import type {
  LedgerStagedCell,
  LedgerStagedCheckRequest,
  LedgerStagedCheckResult,
  LedgerStagedDraft,
  LedgerStagedRow,
  LedgerStagedRowAnswer,
} from "./ledgerMovementOperations";
import { ledgerLanguage } from "./ledgerLanguage";
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
  drafts: ReadonlyMap<string, LedgerStagedCheckResult["drafts"][number]>;
  categories: ReadonlyMap<string, { business: boolean; mixed: boolean }>;
  /** The sentence for a business share no percentage reads, as served and in
   * the language it was served in; null where nothing was asked. */
  shareRefusal: { words: string; language: string } | null;
};

export function indexCheck(result: LedgerStagedCheckResult): StagedCheck {
  return {
    rows: new Map(result.rows.map((row) => [row.transaction_id, row])),
    drafts: new Map(result.drafts.map((draft) => [draft.key, draft])),
    categories: new Map(
      result.categories.map(({ category, business, mixed }) => [
        category,
        { business, mixed },
      ]),
    ),
    shareRefusal: {
      words: result.share_refusal_words,
      language: result.share_refusal_words_language,
    },
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
    // Asked in the language the page shows, so its sentences come in it.
    const language = ledgerLanguage();
    const answer = readAnswer(
      await port.submit(
        "ledger.staged.check",
        language === null ? request : { ...request, output_language: language },
      ),
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
  shareRefusal: null,
};

export class StagedCheckSession extends ReadSessionScheduler<
  LedgerStagedCheckRequest,
  string,
  LedgerStagedCheckResult,
  StagedCheck,
  CheckView
> {
  constructor(
    ask: (request: LedgerStagedCheckRequest) => Promise<CheckReply>,
    pauseMs = PAUSE_MS,
  ) {
    super({
      ask,
      keyOf: (request) => JSON.stringify(request),
      answer: indexCheck,
      present: (view) => view,
      empty: (request) =>
        NOTHING_ASKED(request) ? { answer: NOTHING_CHECKED } : null,
      initial: IDLE,
      pauseMs,
    });
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
