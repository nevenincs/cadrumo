---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove acquisition-lock cleanup is target scoped and repeatable with real lock files

## Scope

- `src/cadrumo/application/auth/tests/test_acquisition_lock.py`

## Description

This is a reconciliation record. The work it documents was executed under the
originating campaign feature stem before this plan existed; it was not
re-executed here. The originating execution record is the `S46` step record of
the `cli-authority-verb-conformance` campaign, whose action text this step row
carries verbatim.

- Add real-lock-file tests proving acquisition-lock cleanup is target-scoped and repeatable.
- Prove clearing one provider's lock leaves an unrelated provider's live lock file intact.
- Prove clearing one bucket's lock leaves the same provider's lock for another bucket intact.
- Prove clearing a target repeatedly removes the real lock once, then reports absence truthfully on the second and third calls without error.

## Outcome

All three proofs exist at HEAD.
`src/cadrumo/application/auth/tests/test_acquisition_lock.py` declares
`test_clear_auth_acquisition_lock_is_target_scoped_across_providers`,
`test_clear_auth_acquisition_lock_is_target_scoped_across_buckets`, and
`test_clear_auth_acquisition_lock_is_repeatable`, alongside the four prior
lock-behaviour tests, for seven nodes in the module.

Attribution is a single clean commit: `3702b24953`, "test(auth): prove
acquisition-lock cleanup is target-scoped and repeatable", dated 2026-07-17. A
content search of the file's history attributes the test names to that commit
and no other.

The originating record reports the focused module passing at seven tests with
clean Ruff, writing and inspecting real crash-recoverable lock files on disk
with no mocks.

## Notes

Substantiated without reservation: all three named test nodes are present at
HEAD and one commit introduced them.

The verification figures quoted above are transcribed from the originating
record and were not re-run for this reconciliation.

The originating record notes that acquisition-lock paths are keyed by both
bucket id and provider kind, so scoped cleanup is naturally target-specific, and
that the clear operation returns the pre-clear status and treats an absent lock
as a truthful no-op, which is what the repeatability proof asserts. No source
change was required.
