---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S13'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Make recovery create refuse an existing enrollment and rotate require an existing enrollment

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`

## Description

- Make `recovery_create` refuse with a typed `SecretStoreError` when a recovery envelope already exists at the target path.
- Make `recovery_rotate` refuse with a typed `SecretStoreError` when no recovery envelope is enrolled yet.
- Route both through one shared `_enroll_recovery` helper keyed by the enrollment mode so the precondition is the only difference between them.

## Outcome

Create and rotate carry mutually exclusive, honest preconditions: create is first-enrollment-only and rotate is replace-only. A refused create leaves the existing envelope byte-identical; a refused rotate writes nothing.

Evidence attributed at HEAD. Commit `b1d80821c9` (2026-07-17) is the same commit that introduced the facade operations. In `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py` at HEAD, `_enroll_recovery` computes `already_enrolled` from the envelope path and raises `SecretStoreError` on the create-with-existing-enrollment branch and again on the rotate-without-enrollment branch. Both refusals fire before `get_master_key` is called, so no master-key access or envelope write is reached on the refused path. Both preconditions are covered by real-file tests in `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py`: `test_recovery_create_refuses_existing_enrollment` and `test_recovery_rotate_requires_existing_enrollment`. That file collects 25 tests and reports 25 passed.

## Notes

Documentation reconciliation only; the step was not re-executed. The originating record `S72` under the predecessor campaign stem carries an identical heading and identical scope file, so the content map to `S13` is exact despite the differing step number.

The refusals reuse the registry-bound `SecretStoreError` rather than minting new error codes, which is why no error-registry change appears in the attributed commit.

The `date` frontmatter is deliberately the landing date `2026-07-17`, not the reconciliation date `2026-07-25`.

No substantiation gap for this step.
