import { appendFileSync } from "node:fs";
import { windowLanguage } from "./strings";
import type { LedgerRow } from "../../src/shell/ledger";
import { answerStagedCheck } from "../../src/dev/ledgerStagedCheckFixture";
import recorded from "@fixtures/ledger-staged-check/ledgerStagedCheck.json" with { type: "json" };
import {
  indexCheck,
  stagedCheckRequest,
  type StagedCheck,
} from "../../src/shell/ledgerStagedCheck";
import type { StagedContent } from "../../src/shell/ledgerStage";
import {
  planApply,
  type LedgerPlan,
  type PlanContext,
} from "../../src/shell/ledgerPlan";

// Each line captured here has the form of a line in
// dev/fixtures/ledger-staged-check-questions/questions.jsonl, the questions
// scripts/ledger_staged_check.py answers into the recording.
const capture = process.env.CADRUMO_STAGED_CHECK_UNRECORDED;
if (capture)
  (
    globalThis as {
      __stagedCheckUnrecorded?: (kind: string, question: string) => void;
    }
  ).__stagedCheckUnrecorded = (kind, question) =>
    appendFileSync(capture, `${JSON.stringify({ kind, question })}\n`);

/** What the backend answered, as recorded, for `content` over `rows`. A
 * question the recording does not hold fails the test rather than guessing. */
export function recordedCheck(
  content: StagedContent,
  rows: ReadonlyMap<string, LedgerRow>,
  also: { ids?: readonly string[]; categories?: readonly string[] } = {},
): StagedCheck {
  const request = stagedCheckRequest(content, rows, also);
  const result = answerStagedCheck(request, (id) => rows.get(id), "p");
  if (!result)
    throw new Error(
      "The staged check recording does not hold this question; capture it with CADRUMO_STAGED_CHECK_UNRECORDED, append the captured line to dev/fixtures/ledger-staged-check-questions/questions.jsonl and run `just fixtures-seed ledger-staged-check` (scripts/ledger_staged_check.py).",
    );
  return indexCheck(result);
}

/** A blocker as a plan holds it, with the sentences the backend said for its
 * kind in the language a read without one is answered in, as recorded. */
export function servedBlocker(kind: string, fields?: readonly string[]) {
  const said = (
    recorded.words.blockers as Record<
      string,
      Record<string, { words: string; fix_words: string }>
    >
  )[kind]!.es!;
  return {
    kind,
    ...(fields ? { fields } : {}),
    words: said.words,
    fixWords: said.fix_words,
    wordsLanguage: "es",
  };
}

/** The sentences the backend said for a blocker kind, as recorded, in the
 * language the window under test speaks: what the review shows the person. */
export function servedBlockerSentences(kind: string) {
  const said = (
    recorded.words.blockers as Record<
      string,
      Record<string, { words: string; fix_words: string }>
    >
  )[kind]![windowLanguage]!;
  return { words: said.words, fixWords: said.fix_words };
}

/** `planApply` with the recorded answer for exactly `content` over the
 * context's rows. */
export function planRecorded(
  content: StagedContent,
  context: Omit<PlanContext, "check">,
): LedgerPlan {
  return planApply(content, {
    ...context,
    check: recordedCheck(content, context.rows),
  });
}
