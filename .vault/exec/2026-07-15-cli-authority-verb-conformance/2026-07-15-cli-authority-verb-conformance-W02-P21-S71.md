---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S71'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Expose distinct recovery status, create, rotate, verify, and recover application operations

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`

## Description

- Add five distinct recovery lifecycle operations to the master-key facade: `recovery_status`, `recovery_create`, `recovery_rotate`, `recovery_verify`, and `recovery_recover`.
- Add typed result records carrying only non-secret data: `RecoveryLifecycleStatus`, `RecoveryEnrollmentOutcome`, `RecoveryVerifyOutcome`, `RecoveryRecoverOutcome`, and the `RecoveryEnrollmentMode` enum.
- Compose the operations over the existing BIP-39 primitives without re-implementing the envelope write path.

## Outcome

The facade now owns the operator-facing recovery lifecycle as five named operations. Status is read-only; create/rotate stage a candidate and commit after a verified retype; verify and recover read the envelope and rewrap the master key respectively. All operations return typed records that never carry the mnemonic or master key.

## Notes

The operations are the backend authority for the later CLI cutover (`W04.P12`); the application custody module and CLI are migrated in that wave. The pre-existing low-level exports remain until then to keep the current consumers compiling.
