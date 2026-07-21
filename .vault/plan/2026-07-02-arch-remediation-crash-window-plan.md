---
tags:
  - '#plan'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-02-aeat-architecture-review-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
  - '[[2026-07-02-arch-remediation-crash-window-reference]]'
  - '[[2026-07-06-arch-remediation-crash-window-research]]'
---
# `arch-remediation-crash-window` plan

### Phase `P01` - VERIFY-cell resolution

For each VERIFY row in the crash-window matrix confirm the actual inter-store write ordering at HEAD and update the reference document body with the findings, resolving each cell to a confirmed guarantee or a documented non-goal.

- [x] `P01.S01` - Confirm the create-profile write ordering at HEAD and resolve the rollback-covers-every-window-including-K-without-S cell, updating the reference body with the finding; `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`.
- [x] `P01.S02` - Confirm the rename-profile cross-store ordering at HEAD and resolve the repair-re-syncs-manifest-from-SQLite cell, updating the reference body with the finding; `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`.
- [x] `P01.S03` - Confirm the hard-delete ordering at HEAD and resolve the partial-directory-detection-in-repair-integrity cell, updating the reference body with the finding; `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`.
- [x] `P01.S04` - Confirm the bundle-export ordering at HEAD and resolve the archive-checkpoints-or-includes-wal-sidecar cell, updating the reference body with the finding; `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`.
- [x] `P01.S05` - Confirm the bundle-import ordering at HEAD and resolve the staging-cleanup cell, updating the reference body with the finding; `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`.
- [x] `P01.S06` - Confirm the attachment-and-evidence-put ordering at HEAD and resolve the orphan-blob-GC-sweep-exists-or-declared-non-goal cell, updating the reference body with the finding; `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`.
- [x] `P01.S07` - Confirm the master-key rotation ordering at HEAD and resolve the mixed-key window across envelope files, blob manifests, and the keystore, updating the reference body with the finding; `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`.

### Phase `P02` - crash-injection tests

Author one crash-injection test per confirmed window using the anti-tautology pattern against the existing repair verbs, starting with the highest-value mixed-key rotation window across envelope files, blob manifests, and the keystore.

- [x] `P02.S08` - Author the mixed-key rotation crash-injection test first, interrupting rotation across envelope files, blob manifests, and the keystore and proving the probe-skip re-run recovers every partial state, using real adapters and simulating the interruption point rather than patching the primitives; `src/aeat/adapters/persistence/storage/tests/test_rotation_crash_windows.py`.
- [x] `P02.S09` - Author the create-profile crash-injection test proving the atomic-create rollback removes partial buckets at every window including K-without-S; `src/aeat/adapters/persistence/storage/tests/test_bucket_crash_windows.py`.
- [x] `P02.S10` - Author the rename-profile crash-injection test proving the diagnostics detect label drift and the repair re-syncs the manifest from the authoritative SQLite record; `src/aeat/adapters/persistence/storage/tests/test_bucket_crash_windows.py`.
- [x] `P02.S11` - Author the hard-delete crash-injection test proving readiness refuses a half-removed bucket and the repair detects partial-directory removal; `src/aeat/adapters/persistence/storage/tests/test_bucket_crash_windows.py`.
- [x] `P02.S12` - Author the bundle-export crash-injection test proving the atomic rename yields no torn archive on a truncated tmp write; `src/aeat/adapters/persistence/storage/tests/test_bundle_crash_windows.py`.
- [x] `P02.S13` - Author the bundle-import crash-injection test proving an aborted prefix is invisible to the manifest pointer and the staging directory is cleaned up; `src/aeat/adapters/persistence/storage/tests/test_bundle_crash_windows.py`.
- [x] `P02.S14` - Author the attachment-put crash-injection test proving an orphan blob is unreferenced and harmless, and pin the GC-sweep guarantee or the declared non-goal resolved in P01; `src/aeat/adapters/persistence/storage/tests/test_attachment_crash_windows.py`.

### Phase `P03` - WAL-sidecar accounting

Assert every at-rest plaintext-scan surface and the sealed-archive writer account for the SQLite -wal sidecar so no committed rows are silently absent.

- [x] `P03.S15` - Assert every at-rest plaintext-scan surface reads the SQLite -wal sidecar so no committed-but-uncheckpointed rows are silently absent from the scan; `src/aeat/adapters/persistence/storage/tests/test_wal_sidecar_accounting.py`.
- [x] `P03.S16` - Assert the sealed-archive writer checkpoints or includes the -wal sidecar so a sealed bundle carries every committed row; `src/aeat/adapters/persistence/storage/tests/test_wal_sidecar_accounting.py`.

## Description

This plan discharges deferral register item D11 (audit finding
persistence-multi-store-crash-windows), turning the crash-window matrix in the
crash-window reference into verified, tested guarantees. A profile bucket's
durable state spans four sibling stores plus a lock (the plaintext manifest, the
encrypted SQLite database and its `-wal` sidecar, the content-addressed blob
store, and the keystore); every single write is atomic, but the composed verbs'
inter-store orderings were convention-guarded and the crash-window matrix was not
itself a tested artefact.

Phase P01 resolves each VERIFY cell in the reference matrix: for each composed
verb (create, rename, hard delete, bundle export, bundle import, attachment put,
master-key rotation) the executor confirms the actual write ordering at HEAD and
updates the reference document body with the finding, resolving every cell to
either a confirmed guarantee or a documented non-goal (reference body edits are
permitted prose). Phase P02 authors one crash-injection test per confirmed
window using the anti-tautology pattern against the existing repair verbs, and
the mixed-key rotation window (envelope files, blob manifests, and the keystore)
comes first because it is the highest-value row, the one place a crash currently
leaves states no gate has enumerated. Phase P03 pins the WAL-sidecar accounting:
every at-rest plaintext-scan surface and the sealed-archive writer must handle the
`-wal` sidecar so no committed rows are silently absent.

The reference is explicit that the matrix is a worklist, not gospel: P01's HEAD
confirmation precedes every test, and a cell that resolves to a non-goal is
documented as such rather than tested. All tests use real adapters (real
encrypted SQLite, real blob store, real keystore); crash injection simulates the
interruption point and never patches or mocks the storage primitives, per the
roundtrip-discipline anti-tautology rule.

## Steps

## Parallelization

P01 precedes P02 by hard ordering: no crash-injection test is authored until its
window's VERIFY cell is resolved against HEAD, because a test written before the
ordering is confirmed risks proving the wrong window. Within P01 the seven
VERIFY-cell resolutions are independent reads of different composed verbs and
could parallelize, but they all edit the single reference document body, so they
run under one owner in sequence to avoid reference-body merge collisions. In P02
the mixed-key rotation test (P02.S08) is authored first per the reference's
highest-value designation; the remaining injection tests are independent across
distinct test modules and parallelize once their P01 cells are confirmed. P03 is
independent of P02 and can land alongside it. A window whose P01 cell resolves to
a documented non-goal drops its P02 test (the attachment orphan-blob step is the
likely instance). This campaign is confined to the persistence storage adapter
test surface plus the reference document; it does not touch production code or
any contended orchestrator file.

## Verification

- Every VERIFY cell in the reference matrix resolves to a confirmed guarantee or
  a documented non-goal, with the reference body updated to record the HEAD
  finding (P01.S01 through P01.S07).
- One crash-injection test exists per confirmed window, each using the
  anti-tautology pattern against the existing repair verbs with real adapters and
  no patched primitives; the mixed-key rotation test recovers every partial state
  across the three stores (P02.S08).
- Every at-rest plaintext-scan surface and the sealed-archive writer account for
  the `-wal` sidecar (P03.S15, P03.S16).
- Each crash-injection test proves detection or recovery by simulating the
  interruption, not by asserting against an un-simulated window.
- The plan is complete when every Step is closed and each Step carries an exec
  record per the plan-closure discipline.
