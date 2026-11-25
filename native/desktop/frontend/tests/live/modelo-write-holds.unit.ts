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

test("a wallet write excludes declarations until its exact hold is released", () => {
  const work = declarationWriteKey("unit");
  const holds = createModeloWriteHolds();
  const lease = holds.begin(walletWriteKey)!;
  assert.equal(holds.begin(work), null);
  holds.unknown(lease, "operation");
  const unknown = holds.get(walletWriteKey)!;
  assert.equal(holds.blocking(work), unknown);
  assert.equal(holds.begin(work), null);
  holds.needsRead(lease);
  assert.equal(holds.begin(work), null);
  holds.readCompleted(unknown);
  assert.equal(holds.begin(work), null);
  // A declaration read must not mistake a wallet blocker for its own hold.
  assert.equal(holds.get(work), undefined);
  holds.readCompleted(holds.get(walletWriteKey)!);
  assert.ok(holds.begin(work));
});

const walletReader = (workUnitId: string, readsIvaWallet?: boolean) => ({
  workUnitId,
  label: workUnitId,
  filingYear: YEAR,
  ...(readsIvaWallet === undefined ? {} : { readsIvaWallet }),
});
const stopped = (operationId: string) => ({
  operation_id: operationId,
  definition_id: "modelo.work.calculate",
  effect: "unknown" as const,
  refusal_words: null,
});

for (const readsIvaWallet of [true, undefined])
  test(`a declaration that ${readsIvaWallet ? "reads" : "may read"} the wallet locks it only while its operation may still run`, () => {
    const work = declarationWriteKey("unit");
    const holds = createModeloWriteHolds();
    const lease = holds.begin(work, walletReader("unit", readsIvaWallet))!;
    assert.equal(holds.begin(walletWriteKey), null);
    holds.unknown(lease, "operation");
    assert.equal(holds.blocking(walletWriteKey), holds.get(work));
    // Stopped: the journal proved the operation ended, so nothing is in flight.
    holds.unknown(lease, "operation", stopped("operation"));
    assert.equal(holds.blocking(walletWriteKey), undefined);
    // Settled or refused: only the declaration's own reads are stale.
    holds.needsRead(lease, false, "refused");
    assert.equal(holds.blocking(walletWriteKey), undefined);
    // The declaration itself stays held until its own recovery.
    assert.equal(holds.blocking(work), holds.get(work));
    assert.equal(holds.begin(work), null);
    const wallet = holds.begin(walletWriteKey);
    assert.ok(wallet);
    assert.equal(holds.get(work)?.phase, "refresh");
  });

test("a declaration whose served form reads no IVA wallet never locks it", () => {
  const work = declarationWriteKey("retenciones");
  const holds = createModeloWriteHolds();
  const lease = holds.begin(work, walletReader("retenciones", false))!;
  assert.equal(holds.blocking(walletWriteKey), undefined);
  holds.unknown(lease, "operation");
  assert.equal(holds.blocking(walletWriteKey), undefined);
  assert.ok(holds.begin(walletWriteKey));
  assert.equal(holds.get(work)?.phase, "unknown");
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

test("a new calculation attempt retires the reviewed failure's words before it asks for anything", async () => {
  const holds = createModeloWriteHolds();
  const lease = holds.begin(workTarget)!;
  holds.unknown(lease, failedCalculation.operation_id, failedCalculation);
  await holds.reviewCalculation(
    holds.get(workTarget)!,
    async () => true,
    () => true,
  );
  let published = 0;
  holds.subscribe(() => published++);
  // The person presses Calcular again; the evidence dialog opens before any
  // write is admitted, and must not repeat the earlier attempt's words.
  holds.newAttempt(workTarget);
  assert.equal(holds.reviewedFailure(workTarget), undefined);
  assert.equal(published, 1);
  assert.equal(holds.snapshot().length, 0);
  // Nothing is admitted or held by the attempt itself.
  assert.notEqual(holds.begin(workTarget), null);
});

test("a new attempt leaves another declaration's reviewed failure and every hold alone", async () => {
  const holds = createModeloWriteHolds();
  const other = declarationWriteKey("work-two");
  const lease = holds.begin(other)!;
  holds.unknown(lease, failedCalculation.operation_id, failedCalculation);
  await holds.reviewCalculation(
    holds.get(other)!,
    async () => true,
    () => true,
  );
  const running = holds.begin(workTarget)!;
  holds.newAttempt(workTarget);
  assert.equal(
    holds.reviewedFailure(other)?.refusal_words,
    failedCalculation.refusal_words,
  );
  assert.equal(holds.get(workTarget)?.id, running.id);
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
