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
