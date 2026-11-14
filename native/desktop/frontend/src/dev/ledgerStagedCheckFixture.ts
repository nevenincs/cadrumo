// `ledger.staged.check` for the fixtures: what the real backend answered for
// each stored movement and staged request, recorded in
// the generated `ledgerStagedCheck.json` and looked up by exactly what was asked. It
// decides nothing: a question not recorded answers null, which the page takes
// as a ledger that did not answer. A test in the owning Python package holds
// every recorded answer equal to the live one and records new questions.

import type { LedgerRow, OutputLanguage } from "../shell/ledger";
import type {
  LedgerStagedCheckRequest,
  LedgerStagedCheckResult,
} from "../shell/ledgerMovementOperations";
import type {
  LedgerStagedDraft,
  LedgerStagedRow,
  LedgerStagedBlocker,
  LedgerStagedRowAnswer,
} from "../shell/ledgerMovementCheckContract";
import { STAGE_FIELDS, storedFieldValue } from "../shell/ledgerStage";
import entryOptions from "@fixtures/ledger-entry-options/ledgerEntryOptions.json" with { type: "json" };
import recorded from "@fixtures/ledger-staged-check/ledgerStagedCheck.json" with { type: "json" };

type RecordedRows = Record<
  string,
  Omit<LedgerStagedRowAnswer, "transaction_id">
>;
type RecordedDrafts = Record<
  string,
  Omit<LedgerStagedCheckResult["drafts"][number], "key">
>;

type RecordedWords = {
  blockers: Record<
    string,
    Record<string, { words: string; fix_words: string }>
  >;
  share_refusal: Record<string, string>;
};
/** The language a read without one is answered in, as the backend's. */
const DEFAULT_LANGUAGE: OutputLanguage = "es";

/** A recorded blocker with the sentences recorded for its kind in the
 * language asked: the sentences depend on the kind and the language alone. */
function inLanguage(
  blocker: LedgerStagedBlocker,
  language: OutputLanguage,
): LedgerStagedBlocker {
  const said = (recorded.words as RecordedWords).blockers[blocker.kind]?.[
    language
  ];
  return said ? { ...blocker, ...said, words_language: language } : blocker;
}

/** Told of each question the recording does not hold, so it can be recorded. */
type Unrecorded = (kind: "row" | "draft", question: string) => void;
const unrecordedHook = () =>
  (globalThis as { __stagedCheckUnrecorded?: Unrecorded })
    .__stagedCheckUnrecorded;

/** What the answer about a movement rests on: all it stores of what can be
 * staged, its lifecycle and evidence, and what was asked. The id is left out
 * since no answer rests on it. */
export function rowQuestion(row: LedgerRow, asked: LedgerStagedRow): string {
  const stored: Record<string, string | null> = {};
  for (const field of STAGE_FIELDS)
    stored[field] = storedFieldValue(row, field) ?? null;
  return JSON.stringify({
    stored,
    lifecycle: row.transaction.lifecycle_state,
    evidence: row.transaction.purchase_invoice_evidence_id !== null,
    cells: asked.cells,
    evidence_staged: asked.evidence_staged,
    m210_staged: asked.m210_staged,
  });
}

export const draftQuestion = (draft: LedgerStagedDraft) =>
  JSON.stringify(draft.fields);

const family = (name: string): readonly string[] =>
  entryOptions.families
    .find((served) => served.family === name)
    ?.options.map((option) => option.value) ?? [];

/** The recorded answer to `request`, or null if any part of it was not
 * recorded. */
export function answerStagedCheck(
  request: LedgerStagedCheckRequest,
  rows: (id: string) => LedgerRow | undefined,
  profileId: string,
): LedgerStagedCheckResult | null {
  const language = request.output_language ?? DEFAULT_LANGUAGE;
  const answers: LedgerStagedRowAnswer[] = [];
  let whole = true;
  for (const asked of request.rows ?? []) {
    const row = rows(asked.transaction_id);
    if (!row) {
      answers.push({
        ...(recorded.absent as Omit<LedgerStagedRowAnswer, "transaction_id">),
        transaction_id: asked.transaction_id,
      });
      continue;
    }
    const question = rowQuestion(row, asked);
    const answer = (recorded.rows as unknown as RecordedRows)[question];
    if (answer)
      answers.push({
        ...answer,
        blockers: answer.blockers.map((blocker) =>
          inLanguage(blocker, language),
        ),
        transaction_id: asked.transaction_id,
      });
    else {
      whole = false;
      unrecordedHook()?.("row", question);
    }
  }
  const drafts: LedgerStagedCheckResult["drafts"] = [];
  for (const draft of request.drafts ?? []) {
    const question = draftQuestion(draft);
    const answer = (recorded.drafts as unknown as RecordedDrafts)[question];
    if (answer)
      drafts.push({
        key: draft.key,
        ...answer,
        blockers: answer.blockers.map((blocker) =>
          inLanguage(blocker, language),
        ),
      });
    else {
      whole = false;
      unrecordedHook()?.("draft", question);
    }
  }
  if (!whole) return null;
  const known = family("spending_category");
  const shared = family("usage_ratio_category");
  return {
    profile_id: profileId,
    input_digest: "recorded",
    rows: answers,
    drafts,
    categories: (request.categories ?? []).map((category) => ({
      category,
      business: known.includes(category),
      mixed: known.includes(category) && shared.includes(category),
    })),
    share_refusal_words: (recorded.words as RecordedWords).share_refusal[
      language
    ]!,
    share_refusal_words_language: language,
  };
}
