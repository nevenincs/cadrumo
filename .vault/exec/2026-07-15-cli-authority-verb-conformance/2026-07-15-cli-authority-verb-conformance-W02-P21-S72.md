---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S72'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Make recovery create refuse an existing enrollment and rotate require an existing enrollment

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`

## Description

- Make `recovery_create` refuse with a typed `SecretStoreError` when a recovery envelope already exists at the target path.
- Make `recovery_rotate` refuse with a typed `SecretStoreError` when no recovery envelope is enrolled yet.
- Route both through one shared `_enroll_recovery` helper keyed by the enrollment mode so the precondition is the only difference.

## Outcome

Create and rotate now have mutually exclusive, honest preconditions: create is enrollment-first-time-only and rotate is replace-only. A refused create leaves the existing envelope byte-identical; a refused rotate writes nothing.

## Notes

Reused the registry-bound `SecretStoreError` rather than adding new error codes, keeping the change within the phase's scoped files (the error registry is out of scope for this phase).
