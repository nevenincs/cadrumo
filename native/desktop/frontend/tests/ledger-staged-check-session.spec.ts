import { expect, test } from "@playwright/test";
import type {
  LedgerStagedCheckRequest,
  LedgerStagedCheckResult,
} from "../src/shell/ledgerMovementOperations";
import {
  StagedCheckSession,
  type CheckReply,
} from "../src/shell/ledgerStagedCheck";

// How the page holds the ledger's answer about staged work: the answer belongs
// to the exact request, a stale reply says nothing, and no answer is no answer.
// No rule is tested here; the answers are opaque to the session.

const request = (id: string): LedgerStagedCheckRequest => ({
  rows: [
    {
      transaction_id: id,
      cells: [],
      evidence_staged: false,
      m210_staged: false,
    },
  ],
  drafts: [],
  categories: [],
});
const result = (digest: string): LedgerStagedCheckResult => ({
  profile_id: "p",
  input_digest: digest,
  rows: [],
  drafts: [],
  categories: [{ category: digest, business: true, mixed: false }],
  share_refusal_words: "A sentence about a share.",
  share_refusal_words_language: "en",
});

function held() {
  const replies: ((reply: CheckReply) => void)[] = [];
  const asked: LedgerStagedCheckRequest[] = [];
  const session = new StagedCheckSession((sent) => {
    asked.push(sent);
    return new Promise((resolve) => replies.push(resolve));
  }, 0);
  return { session, replies, asked };
}
const settled = () => new Promise((resolve) => setTimeout(resolve, 5));
const answered = (session: StagedCheckSession, digest: string) =>
  session.snapshot().current?.categories.has(digest) ?? false;

test("a reply to an older request is not taken for the newer one, which is then asked", async () => {
  const { session, replies, asked } = held();
  session.want(request("a"));
  await settled();
  session.want(request("b"));
  await settled();
  replies[0]!({ kind: "answer", result: result("old") });
  await settled();
  expect(session.snapshot().current).toBeNull();
  expect(session.snapshot().updating).toBe(true);
  expect(asked.map((sent) => sent.rows[0]!.transaction_id)).toEqual(["a", "b"]);
  replies[1]!({ kind: "answer", result: result("new") });
  await settled();
  expect(answered(session, "new")).toBe(true);
});

test("a failed read leaves no answer to act on, and asking again can bring one", async () => {
  const { session, replies } = held();
  session.want(request("a"));
  await settled();
  replies[0]!({ kind: "failed" });
  await settled();
  expect(session.snapshot()).toMatchObject({
    current: null,
    shown: null,
    failed: true,
    updating: false,
  });
  session.retry();
  await settled();
  replies[1]!({ kind: "answer", result: result("again") });
  await settled();
  expect(answered(session, "again")).toBe(true);
  expect(session.snapshot().failed).toBe(false);
});

test("a thrown ask is the same failure as no answer", async () => {
  const session = new StagedCheckSession(
    () => Promise.reject(new Error("host went away")),
    0,
  );
  session.want(request("a"));
  await settled();
  await settled();
  expect(session.snapshot()).toMatchObject({ current: null, failed: true });
});

test("the last answer stays on show while a newer one is awaited, but is not current", async () => {
  const { session, replies } = held();
  session.want(request("a"));
  await settled();
  replies[0]!({ kind: "answer", result: result("first") });
  await settled();
  session.want(request("b"));
  const view = session.snapshot();
  expect(view.current).toBeNull();
  expect(view.shown?.categories.has("first")).toBe(true);
  expect(view.updating).toBe(true);
});

test("nothing staged needs no read and answers at once", async () => {
  const { session, asked } = held();
  session.want({ rows: [], drafts: [], categories: [] });
  await settled();
  expect(asked).toEqual([]);
  expect(session.snapshot().current).not.toBeNull();
  expect(session.snapshot().updating).toBe(false);
});

test("the same request is not asked twice", async () => {
  const { session, replies, asked } = held();
  session.want(request("a"));
  await settled();
  replies[0]!({ kind: "answer", result: result("one") });
  await settled();
  session.want(request("a"));
  await settled();
  expect(asked).toHaveLength(1);
  expect(answered(session, "one")).toBe(true);
});
