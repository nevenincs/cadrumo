// `ledger.rule.trial` for the fixtures: what the real rule engine answered for
// each pattern over the fixture ledger's descriptions, recorded in
// the generated `ledgerRuleTrial.json` and looked up by exactly what was asked. It
// decides nothing: a pattern not recorded answers null, which the page takes as
// a ledger that did not answer. A test in the owning Python package holds every
// recorded answer equal to the live one.
import type { LedgerRuleTrialResult } from "../shell/ledgerMovementOperations";
import type { LedgerRow } from "../shell/ledger";
import recorded from "@fixtures/ledger-recordings/ledgerRuleTrial.json" with { type: "json" };

export function answerRuleTrial(
  pattern: string,
  ids: readonly string[],
  movement: (id: string) => LedgerRow["transaction"] | undefined,
  profileId: string,
): LedgerRuleTrialResult | null {
  const answer = recorded.answers.find(
    (each) => each.description_pattern === pattern,
  );
  if (!answer) return null;
  const outcome = answer.outcome as LedgerRuleTrialResult["outcome"];
  if (outcome !== "matched")
    return { profile_id: profileId, outcome, hits: [], pending: [] };
  const hits = ids.filter((id) => {
    const found = movement(id);
    return (
      found !== undefined &&
      found.lifecycle_state === "ACTIVE" &&
      answer.matches.includes(found.description)
    );
  });
  return {
    profile_id: profileId,
    outcome,
    hits,
    pending: hits.filter(
      (id) => movement(id)!.business_classification === "NOT_YET_PROCESSED",
    ),
  };
}
