import assert from "node:assert/strict";
import test from "node:test";
import {
  createModeloWriteHolds,
  creationWriteKey,
  declarationWriteKey,
  isCreationWriteKey,
  walletWriteKey,
} from "../../src/shell/modeloWriteHolds.ts";

// The keys hold the year without reading it, and node cannot resolve the served
// year recording, so any number stands for it.
const YEAR = 1;

const target = creationWriteKey({
  modelo: "130",
  filing_year: YEAR,
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

test("wallet and declaration writes exclude each other until their exact hold is released", () => {
  const work = declarationWriteKey("unit");
  for (const [first, blocked] of [
    [walletWriteKey, work],
    [work, walletWriteKey],
  ] as const) {
    const holds = createModeloWriteHolds();
    const lease = holds.begin(first)!;
    assert.equal(holds.begin(blocked), null);
    holds.unknown(lease, "operation");
    const unknown = holds.get(first)!;
    assert.equal(holds.blocking(blocked), unknown);
    assert.equal(holds.begin(blocked), null);
    holds.needsRead(lease);
    assert.equal(holds.begin(blocked), null);
    holds.readCompleted(unknown);
    assert.equal(holds.begin(blocked), null);
    // A declaration read must not mistake a wallet blocker for its own hold.
    assert.equal(holds.get(blocked), undefined);
    holds.readCompleted(holds.get(first)!);
    assert.ok(holds.begin(blocked));
  }
});

test("a finished conflicting write retires a preflight even after its hold is removed", () => {
  const work = declarationWriteKey("unit");
  for (const [writer, reader] of [
    [walletWriteKey, work],
    [work, walletWriteKey],
  ] as const) {
    const holds = createModeloWriteHolds();
    const before = holds.admissionVersion(reader);
    const lease = holds.begin(writer)!;
    holds.needsRead(lease);
    holds.readCompleted(holds.get(writer)!);
    assert.equal(holds.blocking(reader), undefined);
    assert.notEqual(holds.admissionVersion(reader), before);
    assert.equal(holds.version(reader), 0);
  }
});

test("wallet exclusion preserves independent declaration and creation admission", () => {
  const holds = createModeloWriteHolds();
  const first = holds.begin(declarationWriteKey("first"))!;
  const second = holds.begin(declarationWriteKey("second"))!;
  assert.ok(first);
  assert.ok(second);
  const before = holds.admissionVersion(second.key);
  const creation = holds.begin(target)!;
  assert.ok(creation);
  holds.notWritten(first);
  assert.equal(holds.begin(walletWriteKey), null);
  holds.notWritten(second);
  assert.ok(holds.begin(walletWriteKey));
  assert.equal(holds.get(target), holds.blocking(target));
  assert.equal(holds.version(second.key), before);
});

test("hold snapshots remain stable between publications and retain recovery ownership", () => {
  const holds = createModeloWriteHolds();
  const empty = holds.snapshot();
  assert.equal(holds.snapshot(), empty);
  const owner = { workUnitId: "303", label: "Modelo 303", filingYear: YEAR };
  const lease = holds.begin(walletWriteKey, owner)!;
  const running = holds.snapshot();
  assert.notEqual(running, empty);
  assert.equal(holds.snapshot(), running);
  holds.unknown(lease, "operation");
  assert.equal(holds.snapshot()[0]?.owner, owner);
  holds.needsRead(lease);
  const refresh = holds.snapshot();
  assert.equal(refresh[0]?.owner, owner);
  holds.readCompleted(running[0]!);
  assert.equal(holds.snapshot(), refresh);
  holds.readCompleted(refresh[0]!);
  assert.equal(holds.snapshot().length, 0);
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
