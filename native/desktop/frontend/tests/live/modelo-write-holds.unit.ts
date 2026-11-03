import assert from "node:assert/strict";
import test from "node:test";
import {
  createModeloWriteHolds,
  creationWriteKey,
  declarationWriteKey,
  isCreationWriteKey,
  walletWriteKey,
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
  const owner = { workUnitId: "303", label: "Modelo 303", filingYear: 2026 };
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
