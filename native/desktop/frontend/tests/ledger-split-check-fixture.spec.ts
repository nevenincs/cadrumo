import { expect, test } from "@playwright/test";
import { answerSplitCheck } from "../src/dev/ledgerSplitCheckFixture";
import type { LedgerSplitCheckRequest } from "../src/shell/ledgerMovementOperations";
import recorded from "@fixtures/ledger-recordings/ledgerSplitCheck.json" with { type: "json" };

// The stand-in stories use for `ledger.split.check`, held to what the real
// backend answered. A test in the owning Python package holds the recording to
// the live answer, so the stand-in cannot drift from the writer unseen.

for (const { parent_amount, parts, answer } of recorded.answers) {
  test(`the stand-in answers as the backend did for ${JSON.stringify([parent_amount, parts])}`, () => {
    expect(
      answerSplitCheck(
        parent_amount,
        parts as LedgerSplitCheckRequest["parts"],
        "profile",
      ),
    ).toEqual({ profile_id: "profile", ...answer });
  });
}
