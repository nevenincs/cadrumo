---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:7bf6a0f84406032947d968fd6af429786bb6da5d76910592f010f5e085d46d15'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `S24 scoped receipt review`

## Scope

Reviewed approved S24 and the S23 resolution across manifest validation, rehearsal receipt
generation, replay, focused tests, plan, and execution records. The review covered unrelated
inventory and byte churn, declared and affected-path drift, stale selected findings, occupied
targets, altered outputs and gates, exact component/manifest identity, transaction races and
rollback, and the new concurrent-disappearance snapshot behavior. No implementation or test
code was modified.

## Findings

### inventory-churn-integration-teeth | medium | The success test does not change object-name inventory

Replay's new unrelated-churn test edits `dev/untracked.txt` and passes the original inventory
object. That file is outside the Python declaration census, so neither the current inventory
digest nor selected graph evidence changes. The production path succeeds under a real
unrelated Python declaration, as an independent probe confirmed, but the committed suite
would not catch reintroduction of receipt/current global-inventory equality. This is the
remaining S23 `end-to-end-churn-teeth` gap.

### scoped-receipt-quality-gates | medium | Current S24 bytes fail format and type checks

Ruff-format reports the new replay success call would be reformatted. Ty reports
`copied_inventory_digest` as `object` where the receipt requires `str`, because the untyped
serialized inventory mapping is indexed without narrowing. Ruff lint and runtime suites pass,
but the approved step's declared static verification is not currently true.

### snapshot-disappearance-teeth | medium | Concurrent disappearance handling has no direct regression test

`_snapshot` now catches `FileNotFoundError` between regular-file validation and hashing and
records the path as absent. This is safe for declared inputs because their required digest
check then refuses, and it gives unrelated paths an observable absence state. No focused test
injects that exact race for either a guarded input or unrelated copied path, so removing the
catch or accidentally accepting a vanished guarded input would not be detected at this
boundary.

No implementation safety defect was found in scoped receipt/replay semantics. Guarded
baseline paths are the union of exact preconditions and the reviewed allowlist; manifest
digest, component identity, finding delta, transformed content, tools, generator outcomes,
and gate outcomes remain independently regenerated. Target occupancy and selected
finding/site/path freshness remain current manifest checks. Immediate pre-mutation snapshots,
per-path expected bytes, mutation intents, and rollback preserve unrelated races rather than
overwriting them. Temporary rehearsal still computes the full changed-path set and refuses
any output outside the reviewed allowlist.

## Recommendations

Add one end-to-end test that authors a manifest, adds an unrelated singular Python
declaration, rescans current inventory, rehearses, asserts receipt inventory differs from the
manifest value, and replays while preserving that file. Narrow the copied inventory digest to
`str` at its serialized boundary and format the replay test. Add deterministic race probes
that make hashing raise `FileNotFoundError`: an unrelated path should be represented as absent
without crashing, while a declared input must be refused before transformation or replay.

## Validation

Manifest plus rehearsal tests passed 69 cases; replay tests passed 58 cases. Ruff lint passed.
Ruff-format and ty each reported one current failure described above. The targeted real
inventory-churn probe passed. Final S24 status is three medium findings and no critical, high,
or low findings.
