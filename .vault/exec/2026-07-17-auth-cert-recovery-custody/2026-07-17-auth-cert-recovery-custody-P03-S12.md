---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:db61c5ca212350527ec0c46934bb64a36ce31a390c57fcf75220e813f72e568e'
step_id: 'S12'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Expose distinct recovery status, create, rotate, verify, and recover application operations

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`

## Description

- Add five distinct recovery lifecycle operations to the master-key facade: `recovery_status`, `recovery_create`, `recovery_rotate`, `recovery_verify`, and `recovery_recover`.
- Add typed result records carrying only non-secret data: `RecoveryLifecycleStatus`, `RecoveryEnrollmentOutcome`, `RecoveryVerifyOutcome`, `RecoveryRecoverOutcome`, and the `RecoveryEnrollmentMode` enum.
- Compose the operations over the existing BIP-39 primitives without re-implementing the envelope write path.

## Outcome

The facade owns the operator-facing recovery lifecycle as five named operations. Status is read-only; create and rotate stage a candidate and commit only after a verified retype; verify reads the envelope and recover rewraps the master key. Every operation returns a typed record that never carries the mnemonic or the master key.

Evidence attributed at HEAD. Commit `b1d80821c9` ("feat: expose file-custody recovery lifecycle authority", 2026-07-17) adds 263 lines to `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`. All five operations exist in that module at HEAD, as do all five typed records; the shared `_enroll_recovery` helper carries the create and rotate bodies. None of the five result models declares a mnemonic or master-key field. The module's `__all__` lists all five operations and all five records. `uv run --no-sync pytest src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py -m "" -q` collects 25 tests and reports 25 passed, matching the count the originating record cited.

## Notes

This record is a documentation reconciliation, not a re-execution. The work landed under the originating campaign feature stem, whose execution record `S71` carries the same heading and the same scope file byte-for-byte; the content map to this plan's `S12` is exact, and the step numbering differs only because the successor plan renumbered. Nothing was re-executed and no production code was touched while writing this record.

The `date` frontmatter is deliberately set to the landing date `2026-07-17` rather than the reconciliation date `2026-07-25`, so this record sorts with the work it describes. Disclosing that backdating here is a direct application of the campaign close honesty review's recommendation on gap-filling records.

No substantiation gap for this step: the commit, the symbols at HEAD, and the passing test count all agree.
