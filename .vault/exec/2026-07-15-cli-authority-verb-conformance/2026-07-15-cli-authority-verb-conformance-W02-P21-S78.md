---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:5e14978826a3a79a1bc94a189f66e13f3688b994c8c2b98bf36a1a115edd1a75'
step_id: 'S78'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove file-only custody and typed keyring or unsecured refusals across the custody matrix

## Scope

- `src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py`

## Description

- Add a file-custody lifecycle test proving the file backend supports status, create, verify, rotate, and recover end to end.
- Add a parametrized test over the keyring and unsecured backends proving every recovery operation refuses with a typed `SecretStoreError` and writes no envelope.

## Outcome

The custody matrix confirms file-only custody: the file backend runs the whole lifecycle, and both non-file backends refuse each of create, rotate, verify, and recover before touching any artefact. `uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py -q` passes the two new tests (three cases).

## Notes

Corrected the relative import depth to reach `cadrumo.adapters` from the application-layer test package (four levels up).
