import assert from "node:assert/strict";
import test from "node:test";
import {
  createModeloWriteHolds,
  creationWriteKey,
  declarationWriteKey,
  isCreationWriteKey,
} from "../../src/shell/modeloWriteHolds.ts";

const target = creationWriteKey({
  modelo: "130",
  filing_year: 2026,
  period_code: "2T",
});

test("a completed write invalidates earlier reads after its hold has gone", () => {
  const holds = createModeloWriteHolds();
  const before = holds.version(target);
  const lease = holds.begin(target)!;
  holds.needsRead(lease);
  holds.readCompleted(holds.get(target)!);
  assert.equal(holds.get(target), undefined);
  assert.notEqual(holds.version(target), before);
  assert.equal(holds.version(declarationWriteKey("other")), 0);
});

test("an operation holds admission synchronously and a retired lease cannot unlock its replacement", () => {
  const holds = createModeloWriteHolds();
  const first = holds.begin(target)!;
  assert.equal(holds.begin(target), null);
  holds.notWritten(first);
  const replacement = holds.begin(target)!;
  holds.notWritten(first);
  assert.equal(holds.get(target)?.id, replacement.id);
});

test("a read begun before authoritative completion cannot unlock an unknown write", () => {
  const holds = createModeloWriteHolds();
  const lease = holds.begin(target)!;
  holds.unknown(lease, "known-operation");
  const before = holds.get(target)!;
  holds.needsRead(lease);
  holds.readCompleted(before);
  assert.equal(holds.get(target)?.phase, "refresh");
  holds.readCompleted(holds.get(target)!);
  assert.equal(holds.get(target), undefined);
});

test("a stale response cannot release a changed refresh hold or a work-unit hold through a creation read", () => {
  const holds = createModeloWriteHolds();
  const creation = holds.begin(target)!;
  const work = holds.begin(declarationWriteKey("unit"))!;
  holds.needsRead(creation);
  holds.needsRead(work);
  const captured = holds
    .snapshot()
    .filter((hold) => isCreationWriteKey(hold.key));
  holds.needsRead(creation, true);
  captured.forEach(holds.readCompleted);
  assert.equal(holds.get(target)?.phase, "refresh");
  assert.equal(holds.get(work.key)?.phase, "refresh");
});

test("an old reader's completion cannot alter the replacement reader's holds", () => {
  const oldReader = createModeloWriteHolds();
  const nextReader = createModeloWriteHolds();
  const previous = oldReader.begin(target)!;
  const current = nextReader.begin(target)!;
  oldReader.needsRead(previous);
  oldReader.readCompleted(oldReader.get(target)!);
  assert.equal(nextReader.get(target)?.id, current.id);
  assert.equal(nextReader.get(target)?.phase, "running");
});

const failedCalculation = {
  operation_id: "a".repeat(64),
  definition_id: "modelo.work.calculate",
  effect: "unknown" as const,
  refusal_words: "The invoice evidence must be reviewed.",
};
const workTarget = declarationWriteKey("work-one");

test("an ordinary declaration read cannot unlock a terminal failed calculation", async () => {
  const holds = createModeloWriteHolds();
  const lease = holds.begin(workTarget)!;
  holds.unknown(lease, failedCalculation.operation_id, failedCalculation);
  const hold = holds.get(workTarget)!;
  holds.readCompleted(hold);
  assert.equal(holds.get(workTarget), hold);
  assert.equal(holds.begin(workTarget), null);
  assert.equal(holds.reviewedFailure(workTarget), undefined);
});

for (const effect of ["unknown", "partial", "updated"] as const)
  test(`explicit review of a stopped calculation with ${effect} effects reads current form, retains warning, and permits a separate new intent`, async () => {
    const holds = createModeloWriteHolds();
    const terminal = { ...failedCalculation, effect };
    const lease = holds.begin(workTarget)!;
    holds.unknown(lease, terminal.operation_id, terminal);
    const hold = holds.get(workTarget)!;
    let reads = 0;
    assert.equal(holds.begin(workTarget), null);
    assert.equal(
      await holds.reviewCalculation(
        hold,
        async () => {
          reads++;
          return true;
        },
        () => true,
      ),
      true,
    );
    assert.equal(reads, 1);
    assert.equal(holds.get(workTarget), undefined);
    assert.equal(
      holds.reviewedFailure(workTarget)?.refusal_words,
      terminal.refusal_words,
    );
    assert.equal(holds.reviewedFailure(workTarget)?.effect, effect);
    assert.equal(
      terminal.effect,
      effect,
      "review never rewrites earlier effect evidence",
    );
    // No new operation was begun by review. A later, separately clicked action
    // obtains a fresh lease; its own backend request remains authoritative.
    assert.equal(holds.snapshot().length, 0);
    const next = holds.begin(workTarget)!;
    assert.notEqual(next.id, hold.id);
    assert.equal(holds.reviewedFailure(workTarget), undefined);
  });

for (const result of [false, "throws"] as const)
  test(`an explicit review whose current form read ${result === false ? "fails" : "throws"} remains held`, async () => {
    const holds = createModeloWriteHolds();
    const lease = holds.begin(workTarget)!;
    holds.unknown(lease, failedCalculation.operation_id, failedCalculation);
    const hold = holds.get(workTarget)!;
    assert.equal(
      await holds.reviewCalculation(
        hold,
        async () => {
          if (result === "throws") throw new Error("unavailable");
          return false;
        },
        () => true,
      ),
      false,
    );
    assert.equal(holds.get(workTarget), hold);
    assert.equal(holds.reviewedFailure(workTarget), undefined);
  });

test("in-flight unknown, unrelated operations, foreign IDs and creation holds cannot enter calculation review", async () => {
  for (const [key, terminal] of [
    [workTarget, undefined],
    [
      workTarget,
      { ...failedCalculation, definition_id: "modelo.work.m303_attestation" },
    ],
    [workTarget, { ...failedCalculation, operation_id: "b".repeat(64) }],
    [target, failedCalculation],
  ] as const) {
    const holds = createModeloWriteHolds();
    const lease = holds.begin(key)!;
    holds.unknown(lease, failedCalculation.operation_id, terminal);
    const hold = holds.get(key)!;
    let read = false;
    assert.equal(
      await holds.reviewCalculation(
        hold,
        async () => {
          read = true;
          return true;
        },
        () => true,
      ),
      false,
    );
    assert.equal(read, false);
    assert.equal(holds.get(key), hold);
  }
});

test("a declaration or reader changed while review was pending cannot release its hold", async () => {
  const holds = createModeloWriteHolds();
  const lease = holds.begin(workTarget)!;
  holds.unknown(lease, failedCalculation.operation_id, failedCalculation);
  const hold = holds.get(workTarget)!;
  let current = true;
  assert.equal(
    await holds.reviewCalculation(
      hold,
      async () => {
        current = false;
        return true;
      },
      () => current,
    ),
    false,
  );
  assert.equal(holds.get(workTarget), hold);
});

test("a stale review cannot release a changed hold or its replacement", async () => {
  for (const replace of [false, true]) {
    const holds = createModeloWriteHolds();
    const lease = holds.begin(workTarget)!;
    holds.unknown(lease, failedCalculation.operation_id, failedCalculation);
    const hold = holds.get(workTarget)!;
    let afterId = hold.id;
    assert.equal(
      await holds.reviewCalculation(
        hold,
        async () => {
          if (replace) {
            holds.notWritten(hold);
            afterId = holds.begin(workTarget)!.id;
          } else {
            holds.unknown(
              hold,
              failedCalculation.operation_id,
              failedCalculation,
            );
            afterId = holds.get(workTarget)!.id;
          }
          return true;
        },
        () => true,
      ),
      false,
    );
    assert.equal(holds.get(workTarget)?.id, afterId);
    assert.notEqual(holds.get(workTarget), undefined);
  }
});
