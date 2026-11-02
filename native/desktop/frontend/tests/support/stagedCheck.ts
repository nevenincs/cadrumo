import { appendFileSync } from "node:fs";
import type { LedgerRow } from "../../src/shell/ledger";
import { answerStagedCheck } from "../../src/dev/ledgerStagedCheckFixture";
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
      "The staged check recording does not hold this question; record it with the Python recording test.",
    );
  return indexCheck(result);
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
