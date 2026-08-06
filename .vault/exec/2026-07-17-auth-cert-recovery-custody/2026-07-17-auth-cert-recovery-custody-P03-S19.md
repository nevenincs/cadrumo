---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:f67eaf5e10a7a1057c13059431e8cc63f15cb15c19e03ba1078b1fc11fb718df'
step_id: 'S19'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove file-only custody and typed keyring or unsecured refusals across the custody matrix

## Scope

- `src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py`

## Description

- Add a file-custody lifecycle test proving the file backend supports status, create, verify, rotate, and recover end to end.
- Add a parametrized test over the keyring and unsecured backends proving every recovery operation refuses with a typed `SecretStoreError` and writes no envelope.

## Outcome

The custody matrix confirms file-only custody: the file backend runs the whole lifecycle, and both non-file backends refuse each of create, rotate, verify, and recover before touching any artefact.

Evidence attributed at HEAD. Commit `e7cb4e84fd` ("test: prove file-only custody across the recovery lifecycle matrix", 2026-07-17) is the attributed landing. At HEAD `src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py` carries both named tests: `test_file_custody_supports_the_full_recovery_lifecycle` and `test_non_file_custody_refuses_every_recovery_operation`, the latter decorated with a parametrize over the keyring and unsecured backends. That parametrization is what makes the pairing with the `_require_file_custody` guard a matrix rather than a single-backend check. Re-run at HEAD, `uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py -m "" -q --no-header` collects 4 tests, all passing: the three cases these two tests contribute plus the one pre-existing `test_every_carried_store_round_trips_through_recovery`. That reconciles exactly with the originating record's "two new tests, three cases".

Two later commits touched this file without changing the contract: `dfd48699c8` reformatted it, and `60fc20aeed` sourced the test passphrase from a shared setting while retiring stale write-inventory entries.

## Notes

Documentation reconciliation only; the tests were not re-authored. The originating record `S78` carries an identical heading and identical scope file, so the map to `S19` is exact.

The keyring-backend case passed in this environment, which is worth recording explicitly because agent sessions here run over an SSH network logon and genuine Windows keyring operations fail with `WinError 1312`. This test does not hit that failure, because it asserts the custody guard refuses the keyring provider before any keychain access is attempted — the refusal is a type check on the resolved provider, not a keyring call. Had the test needed real keychain access it would have been unverifiable in this session; it does not.

The originating record notes an import-depth correction made while authoring, reaching `cadrumo.adapters` from the application-layer test package. That is consistent with the file's location under the application layer and required no production change.

The `date` frontmatter is deliberately the landing date `2026-07-17`, not the reconciliation date `2026-07-25`.

No substantiation gap for this step.
