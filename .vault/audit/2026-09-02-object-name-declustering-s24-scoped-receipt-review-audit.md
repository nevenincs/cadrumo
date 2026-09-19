---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:932a5e13a5c0ef0d012c433eea878732b915696a2bcd9600238ba81f829acd58'
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

## Remediation re-review

Resolved: `scoped-receipt-quality-gates` is closed. The copied serialized inventory digest is
explicitly narrowed to `str`, the amended files are formatted, and Ruff lint, Ruff format,
and ty all pass for the rehearsal/replay implementation and tests.

Resolved: `snapshot-disappearance-teeth` is closed. The focused test forces `sha256_file` to
raise `FileNotFoundError` after regular-file discovery and asserts the exact tracked-absence
snapshot entry. Together with the existing required-input digest and guarded-baseline checks,
this bites the race-handling branch while preserving fail-closed treatment of a vanished
declared input. The focused detector passed.

Open: `inventory-churn-integration-teeth` remains medium. The amended replay fixture now adds
a real Python declaration, but it still supplies the inventory and component captured before
that file was created. It does not rescan the current repository, assert the digest changed,
or derive the component from that fresh inventory. Consequently it proves preservation of a
post-receipt Python file but not acceptance of the freshly rescanned post-churn inventory used
by the CLI. A regression restoring equality against a historical inventory could escape this
test. The earlier disposable probe with fresh inventory continues to support the production
behavior; the remaining defect is detector coverage.

Focused validation passed the amended replay and disappearance cases (2 tests). Ruff lint,
Ruff format, and ty passed. Final S24 status is one medium finding and no critical, high, or
low findings.

## Final closure

Resolved: `inventory-churn-integration-teeth` is closed. The replay integration test now
rescans the repository after creating `dev/concurrent_helper.py`, asserts the current
inventory digest changed, rebuilds the current component, and invokes replay with the fresh
inventory and component while retaining the earlier receipt. The successful replay and exact
preservation assertion now cover genuine unrelated inventory churn through the production
boundary rather than only filesystem byte churn.

The focused detector passed (1 test in 3.59 seconds); Ruff lint, Ruff format, and ty passed for
the amended replay test. Final S24 status is no findings at any severity.
