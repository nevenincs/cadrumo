---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S15'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Restrict recovery to file custody and return typed refusals for keyring and unsecured custody

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`

## Description

- Add a `_require_file_custody` guard that narrows the resolved master-key provider to the file backend and refuses keyring and unsecured providers with typed, remediating `SecretStoreError` refusals.
- Call the guard first in create, rotate, verify, and recover so a non-file custody backend is refused before any envelope or master-key access.

## Outcome

Recovery custody operations run only under file custody. Keyring and unsecured backends receive a typed refusal naming the remediation, and never touch the recovery envelope.

Evidence attributed at HEAD. Commit `b1d80821c9` (2026-07-17) introduced the guard alongside the facade operations. At HEAD `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py` defines `_require_file_custody`, returning the provider only when it is a `FileFallbackMasterKeyProvider` and otherwise raising `SecretStoreError` on three branches: a keyring provider, an unsecured provider, and an unrecognised provider type. The keyring and unsecured refusals both name the remediation explicitly, instructing the operator to set the file secret-store backend and retry, which satisfies the project standard that a refusal must carry the accepted value set rather than a bare rejection. The guard is the first statement of `_enroll_recovery`, so it fires ahead of the enrollment preconditions for both create and rotate, and it is likewise the first statement of `recovery_verify` and `recovery_recover`. The custody matrix is proven end to end in `src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py`, whose `test_non_file_custody_refuses_every_recovery_operation` is parametrized over the keyring and unsecured backends; that file collects 4 tests and passes.

## Notes

Documentation reconciliation only; the step was not re-executed. The originating record `S74` carries an identical heading and identical scope file, so the map to `S15` is exact.

`recovery_status` is deliberately left custody-agnostic and is the one lifecycle operation that does not call the guard. This is not an omission: status is a read-only inspection of the envelope file, and the decision record scopes the file-only restriction to create, rotate, verify, recover, and passphrase change. The originating record states the same rationale, and the code at HEAD matches it.

The `date` frontmatter is deliberately the landing date `2026-07-17`, not the reconciliation date `2026-07-25`.

No substantiation gap for this step.
