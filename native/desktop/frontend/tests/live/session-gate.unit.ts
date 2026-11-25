import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import type { HostCall } from "../../src/shell/hostCall.ts";
import {
  confirmSessionWith,
  endSession,
  firstAfterEnd,
  refuseIfEnded,
  sessionBound,
  sessionEndConfirmed,
  sessionEnded,
  startSession,
} from "../../src/shell/sessionGate.ts";

// The window's one session gate: once it knows the session ended, a command
// only a signed-in session can ask is answered here with the host's own
// refusal and never sent, and a new session opens the gate again. Run with
// `node --test tests/live/session-gate.unit.ts`.

function recording() {
  const sent: string[] = [];
  const call = ((command: string) => {
    sent.push(command);
    return Promise.resolve(null);
  }) as unknown as HostCall;
  return { sent, bound: sessionBound(call) };
}

beforeEach(() => startSession());

test("a session-bound command is sent while the session lasts", async () => {
  const { sent, bound } = recording();
  await bound("aeat_sync_progress", { profile: "A" });
  assert.deepEqual(sent, ["aeat_sync_progress"]);
});

test("after the session ended a session-bound command is refused here and not sent", async () => {
  const { sent, bound } = recording();
  endSession();
  await assert.rejects(bound("ledger_files_pick", {} as never), {
    code: "not_signed_in",
  });
  await assert.rejects(bound("user_profile_household", { language: "en" }), {
    code: "not_signed_in",
  });
  assert.throws(() => refuseIfEnded(), { code: "not_signed_in" });
  assert.deepEqual(sent, []);
});

test("a new session sends session-bound commands again", async () => {
  const { sent, bound } = recording();
  endSession();
  await assert.rejects(bound("aeat_sync_progress", { profile: "A" }));
  startSession();
  assert.equal(sessionEnded(), false);
  refuseIfEnded();
  await bound("aeat_sync_progress", { profile: "A" });
  assert.deepEqual(sent, ["aeat_sync_progress"]);
});

test("an ended session's refusal is first once per operation, and afresh after a new session", () => {
  endSession();
  assert.equal(firstAfterEnd("aeat_sync_progress"), true);
  assert.equal(firstAfterEnd("aeat_sync_progress"), false);
  assert.equal(firstAfterEnd("user_profile_household"), true);
  startSession();
  endSession();
  assert.equal(firstAfterEnd("aeat_sync_progress"), true);
});

test("an end is confirmed only when the sign-in state's read finds the session gone", async () => {
  assert.equal(await sessionEndConfirmed(), false);
  let reads = 0;
  const stillThere = confirmSessionWith(async () => {
    reads += 1;
  });
  assert.equal(await sessionEndConfirmed(), false);
  stillThere();
  const gone = confirmSessionWith(async () => {
    reads += 1;
    endSession();
  });
  assert.equal(await sessionEndConfirmed(), true);
  // A known end needs no read.
  assert.equal(await sessionEndConfirmed(), true);
  assert.equal(reads, 2);
  gone();
});

test("a read that fails confirms nothing", async () => {
  const release = confirmSessionWith(() => Promise.reject(new Error("down")));
  assert.equal(await sessionEndConfirmed(), false);
  release();
});

test("releasing a replaced reader leaves its replacement in place", async () => {
  const first = confirmSessionWith(async () => undefined);
  const second = confirmSessionWith(async () => endSession());
  first();
  assert.equal(await sessionEndConfirmed(), true);
  second();
});
