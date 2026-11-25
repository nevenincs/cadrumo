import { appendFileSync } from "node:fs";
import type { Page } from "@playwright/test";

// The scenario page answers `ledger.staged.check` from the recording and
// tells `__stagedCheckUnrecorded` of every question the recording lacks. In a
// browser that hook lives on the page's window, so a spec run with
// CADRUMO_STAGED_CHECK_UNRECORDED naming a file exposes it there and appends
// each lacking question in the form of
// dev/fixtures/ledger-staged-check-questions/questions.jsonl.

/** Records the staged-check questions `target` asks that the recording does
 * not hold, when CADRUMO_STAGED_CHECK_UNRECORDED names a file. */
export async function captureUnrecordedQuestions(target: Page) {
  const capture = process.env.CADRUMO_STAGED_CHECK_UNRECORDED;
  if (!capture) return;
  await target.exposeFunction(
    "__stagedCheckUnrecorded",
    (kind: string, question: string) => {
      appendFileSync(capture, `${JSON.stringify({ kind, question })}\n`);
    },
  );
}
