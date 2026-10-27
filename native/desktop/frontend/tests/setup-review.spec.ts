import { expect, test } from "@playwright/test";
import {
  browserPlan,
  reviewFailureKey,
  SetupReviewSession,
  type SetupReviewPort,
} from "../src/shell/setupReview";
import type {
  SetupOperationReview,
  SetupReviewCoordinates,
} from "../src/ipc/contract";

const review: SetupOperationReview = {
  kind: "operation_review",
  operation_id: "a".repeat(64),
  interaction_id: "b".repeat(64),
  revision: 3,
  review_digest: "c".repeat(64),
  expires_at: null,
  document: { plan_digest: "exact-role-plan" },
};

function fixture() {
  const calls: {
    action: string;
    review?: SetupReviewCoordinates;
    decision?: string;
  }[] = [];
  const port: SetupReviewPort = {
    read: async () => {
      calls.push({ action: "read" });
      return review;
    },
    claim: async (shown) => {
      calls.push({ action: "claim", review: shown });
      return {
        ...review,
        kind: "operation_review_claimed",
        revision: 4,
        review_digest: "d".repeat(64),
      };
    },
    answer: async (shown, decision) => {
      calls.push({ action: "answer", review: shown, decision });
      return {
        kind: "operation_responded",
        operation_id: shown.operation_id,
        decision,
      };
    },
  };
  return {
    calls,
    port,
    session: new SetupReviewSession(port, () => undefined),
  };
}

for (const decision of ["apply", "reject"] as const) {
  test(`a displayed review needs an explicit claim before ${decision} and uses the successor`, async () => {
    const { session, calls } = fixture();
    await session.read(review.operation_id);
    await session.answer(decision);
    expect(calls.map((call) => call.action)).toEqual(["read"]);
    await session.claim();
    expect(calls[1]?.review).toEqual({
      operation_id: review.operation_id,
      interaction_id: review.interaction_id,
      revision: 3,
      review_digest: review.review_digest,
    });
    await session.answer(decision);
    expect(calls[2]?.review?.revision).toBe(4);
    expect(calls[2]?.review?.review_digest).toBe("d".repeat(64));
    expect(calls[2]?.decision).toBe(decision);
    await session.answer(decision);
    expect(calls).toHaveLength(3);
  });
}

test("stale, claimed-by-another and retired claims discard local response eligibility", async () => {
  for (const code of [
    "stale_revision",
    "review_already_claimed",
    "session_retired",
  ]) {
    const { session, port, calls } = fixture();
    port.claim = async () => {
      throw { code };
    };
    await session.read(review.operation_id);
    await session.claim();
    await session.answer("apply");
    expect(session.state).toEqual({
      review: null,
      claimed: false,
      busy: false,
      failed: true,
      failureCode: code,
      unknownOperationIds: [],
    });
    expect(calls.map((call) => call.action)).toEqual(["read"]);
  }
});

test("an answer lost in transit is never retried from local authority", async () => {
  const { session, port } = fixture();
  let answers = 0;
  port.answer = async () => {
    answers++;
    throw new Error("connection retired after apply");
  };
  await session.read(review.operation_id);
  await session.claim();
  await session.answer("apply");
  await session.answer("apply");
  expect(answers).toBe(1);
  expect(session.state).toEqual({
    review: null,
    claimed: false,
    busy: false,
    failed: false,
    failureCode: "unknown",
    unknownOperationIds: [review.operation_id],
  });
  // Reading a review is not evidence that an uncertain apply did not run.
  await session.read(review.operation_id);
  expect(session.state.unknownOperationIds).toEqual([review.operation_id]);
  await session.claim();
  await session.answer("apply");
  expect(answers).toBe(1);
  expect(session.state.claimed).toBe(false);
});

test("clearing the displayed operation fences a late claim reply", async () => {
  const { session, port } = fixture();
  let finish!: (value: SetupOperationReview) => void;
  port.claim = () =>
    new Promise((resolve) => {
      finish = resolve;
    });
  await session.read(review.operation_id);
  const pending = session.claim();
  session.clear();
  finish({ ...review, kind: "operation_review_claimed", revision: 4 });
  await pending;
  expect(session.state.review).toBeNull();
  expect(session.state.claimed).toBe(false);
});

test("a late read cannot display a previous profile's review after the session is cleared", async () => {
  const { session, port } = fixture();
  let finish!: (value: SetupOperationReview) => void;
  port.read = () =>
    new Promise((resolve) => {
      finish = resolve;
    });
  const pending = session.read(review.operation_id);
  session.clear(); // The mounted review is cleared on profile change or unmount.
  finish(review);
  await pending;
  expect(session.state).toEqual({
    review: null,
    claimed: false,
    busy: false,
    failed: false,
    failureCode: null,
    unknownOperationIds: [],
  });
});

test("only the new operation is displayed when an earlier read arrives late", async () => {
  const { session, port } = fixture();
  let finish!: (value: SetupOperationReview) => void;
  port.read = () =>
    new Promise((resolve) => {
      finish = resolve;
    });
  const old = session.read(review.operation_id);
  session.clear();
  port.read = async () => ({ ...review, operation_id: "e".repeat(64) });
  await session.read("e".repeat(64));
  finish(review);
  await old;
  expect(session.state.review?.operation_id).toBe("e".repeat(64));
  expect(session.state.claimed).toBe(false);
});

test("the human plan preserves exact download facts without changing its canonical document", () => {
  const document = {
    projection: {
      plan_digest: "f".repeat(64),
      plan: {
        contract_version: 3,
        entries: [
          {
            item_id: "browser",
            download_bytes: 12345,
            source_hosts: ["browser.example"],
            destination: "playwright-browsers",
            installs_outside_program: false,
            target_version: "123.0",
            parts: [],
          },
        ],
        known_download_bytes: 12345,
        has_unknown_size: false,
        installs_outside_program: false,
        space: { free_bytes: 50000, required_bytes: 24690, sufficient: true },
      },
    },
  };
  const original = JSON.stringify(document);
  const plan = browserPlan(document, "Browser files");
  expect(plan?.entries[0]).toMatchObject({
    item: "browser",
    download_bytes: 12345,
    source_hosts: ["browser.example"],
    destination: "Browser files",
  });
  expect(plan?.required_bytes).toBe(24690);
  expect(plan?.free_bytes).toBe(50000);
  expect(JSON.stringify(document)).toBe(original);
  expect(
    browserPlan(
      { projection: { plan: { contract_version: 4 } } },
      "Browser files",
    ),
  ).toBeNull();
});

test("claim refusals retain distinct stale, held-elsewhere and retired recovery guidance", () => {
  expect(reviewFailureKey("review_claim_stale")).toBe(
    "desktop.setup_review.failed",
  );
  expect(reviewFailureKey("review_already_claimed")).toBe(
    "desktop.setup_review.claimed_elsewhere",
  );
  expect(reviewFailureKey("response_authority_required")).toBe(
    "desktop.setup_review.authority_lost",
  );
  expect(reviewFailureKey("session_retired")).toBe(
    "desktop.setup_review.authority_lost",
  );
});

test("closing Settings during apply preserves the owned session's eventual uncertain answer", async () => {
  const { session, port } = fixture();
  let rejectAnswer!: (reason: unknown) => void;
  let notifications = 0;
  const closeSettings = session.subscribe(() => {
    notifications++;
  });
  port.answer = () =>
    new Promise((_resolve, reject) => {
      rejectAnswer = reject;
    });
  await session.read(review.operation_id);
  await session.claim();
  const pending = session.answer("apply");
  expect(session.getSnapshot().busy).toBe(true);
  closeSettings(); // The view unsubscribes; the App-owned session remains live.
  const before = notifications;
  rejectAnswer(new Error("apply outcome lost"));
  await pending;
  expect(notifications).toBe(before);
  expect(session.getSnapshot().unknownOperationIds).toEqual([
    review.operation_id,
  ]);
  expect(session.getSnapshot().review).toBeNull();
  expect(session.getSnapshot().claimed).toBe(false);
  const reopened = session.subscribe(() => undefined);
  expect(session.getSnapshot().unknownOperationIds).toEqual([
    review.operation_id,
  ]);
  reopened();
});

test("unknown answer survives the status dialog and return to Settings without restoring authority", async () => {
  const { session, port } = fixture();
  let answers = 0;
  port.answer = async () => {
    answers++;
    throw new Error("answer lost");
  };
  await session.read(review.operation_id);
  await session.claim();
  await session.answer("apply");
  const closeSettings = session.subscribe(() => undefined);
  closeSettings(); // Opening component status unmounts Settings, not its owner.
  const returnToSettings = session.subscribe(() => undefined);
  expect(session.getSnapshot().unknownOperationIds).toEqual([
    review.operation_id,
  ]);
  await session.read(review.operation_id);
  await session.claim();
  await session.answer("apply");
  expect(answers).toBe(1);
  expect(session.getSnapshot().unknownOperationIds).toEqual([
    review.operation_id,
  ]);
  expect(session.getSnapshot().claimed).toBe(false);
  returnToSettings();
});

test("two lost operation answers retain both uncertainties and both local replay fences", async () => {
  const { session, port } = fixture();
  let answers = 0;
  const ids = [review.operation_id, "e".repeat(64)];
  port.read = async (operationId) => ({ ...review, operation_id: operationId });
  port.claim = async (shown) => ({
    ...review,
    ...shown,
    kind: "operation_review_claimed",
    revision: shown.revision + 1,
  });
  port.answer = async () => {
    answers++;
    throw new Error("outcome lost");
  };
  for (const operationId of ids) {
    await session.read(operationId);
    await session.claim();
    await session.answer("apply");
  }
  expect(session.getSnapshot().unknownOperationIds).toEqual(ids);
  const closeSettings = session.subscribe(() => undefined);
  closeSettings();
  const reopened = session.subscribe(() => undefined);
  for (const operationId of ids) {
    await session.read(operationId);
    await session.claim();
    await session.answer("apply");
  }
  expect(answers).toBe(2);
  expect(session.getSnapshot().unknownOperationIds).toEqual(ids);
  expect(session.getSnapshot().claimed).toBe(false);
  reopened();
});
