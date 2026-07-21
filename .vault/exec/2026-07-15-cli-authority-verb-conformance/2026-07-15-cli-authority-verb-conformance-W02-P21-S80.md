---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S80'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Re-export only the explicit passphrase and recovery lifecycle operations

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/__init__.py`

## Description

- Re-export the explicit recovery lifecycle operations and their result records through the master-key package facade: `recovery_status`, `recovery_create`, `recovery_rotate`, `recovery_verify`, `recovery_recover`, and the `RecoveryEnrollmentMode`, `RecoveryLifecycleStatus`, `RecoveryEnrollmentOutcome`, `RecoveryVerifyOutcome`, and `RecoveryRecoverOutcome` types.
- Keep the internal helpers (`atomically_install_verified_recovery`, custody guard) unexported.

## Outcome

The package facade exposes the recovery lifecycle as its public surface. Cross-package consumers can import the operations from the master-key package top level without reaching into private modules.

## Notes

The pre-existing low-level recovery primitives stay exported to keep the current application custody module compiling; that module and the CLI are migrated onto these operations in `W04.P12`.
