import { expect, test } from "@playwright/test";
import type { LedgerRuleTrialResult } from "../src/shell/ledgerMovementOperations";
import {
  RuleTrialSession,
  type RuleTrial,
  type RuleTrialQuestion,
} from "../src/shell/ledgerRuleTrial";

// How the rule dialog holds the backend's answer about a pattern: the backend
// refuses a second trial while one runs, so one is out at a time, the latest
// wins, and a stale reply says nothing.

const ids: readonly string[] = ["row"];
const question = (pattern: string): RuleTrialQuestion => ({ pattern, ids });
const answer = (hit: string): RuleTrial => ({
  kind: "answer",
  result: {
    profile_id: "p",
    outcome: "matched",
    hits: [hit],
    pending: [],
  } satisfies LedgerRuleTrialResult,
});

function held() {
  const replies: ((trial: RuleTrial) => void)[] = [];
  const asked: string[] = [];
  const session = new RuleTrialSession((sent) => {
    asked.push(sent.pattern);
    return new Promise((resolve) => replies.push(resolve));
  }, 0);
  return { session, replies, asked };
}
const settled = () => new Promise((resolve) => setTimeout(resolve, 5));
const found = (trial: RuleTrial) =>
  trial.kind === "answer" ? trial.result.hits[0] : null;

test("only one trial is out while typing goes on, and only the latest is asked next", async () => {
  const { session, replies, asked } = held();
  session.want(question("a"));
  await settled();
  session.want(question("ab"));
  await settled();
  session.want(question("abc"));
  await settled();
  expect(asked).toEqual(["a"]);

  replies[0]!(answer("stale"));
  await settled();
  expect(session.snapshot().kind).toBe("waiting");
  expect(asked).toEqual(["a", "abc"]);

  replies[1]!(answer("latest"));
  await settled();
  expect(found(session.snapshot())).toBe("latest");
});

test("a failed trial of the final pattern shows as failed and asks again only when told", async () => {
  const { session, replies, asked } = held();
  session.want(question("a"));
  await settled();
  replies[0]!({ kind: "failed" });
  await settled();
  expect(session.snapshot().kind).toBe("failed");
  await settled();
  expect(asked).toEqual(["a"]);

  session.retry();
  await settled();
  expect(session.snapshot().kind).toBe("waiting");
  expect(asked).toEqual(["a", "a"]);
  replies[1]!(answer("found"));
  await settled();
  expect(found(session.snapshot())).toBe("found");
});

test("a failure of a question already overtaken is not shown for the latest", async () => {
  const { session, replies, asked } = held();
  session.want(question("a"));
  await settled();
  session.want(question("b"));
  await settled();
  replies[0]!({ kind: "failed" });
  await settled();
  expect(session.snapshot().kind).toBe("waiting");
  expect(asked).toEqual(["a", "b"]);
});

test("going back to an answered pattern shows its answer without asking again", async () => {
  const { session, replies, asked } = held();
  session.want(question("a"));
  await settled();
  replies[0]!(answer("first"));
  await settled();
  session.want({ pattern: "", ids });
  expect(session.snapshot().kind).toBe("waiting");
  session.want(question("a"));
  expect(found(session.snapshot())).toBe("first");
  await settled();
  expect(asked).toEqual(["a"]);
});

test("a rejected ask is the same failure as no answer", async () => {
  const session = new RuleTrialSession(
    () => Promise.reject(new Error("no")),
    0,
  );
  session.want(question("a"));
  await settled();
  expect(session.snapshot().kind).toBe("failed");
});
