---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S74'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Restrict recovery to file custody and return typed refusals for keyring and unsecured custody

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`

## Description

- Add a `_require_file_custody` guard that narrows the resolved master-key provider to the file backend and refuses keyring and unsecured providers with typed, remediating `SecretStoreError` refusals.
- Call the guard first in create, rotate, verify, and recover so a non-file custody backend is refused before any envelope or master-key access.

## Outcome

Recovery and passphrase custody operations run only under file custody. Keyring and unsecured backends receive a typed refusal that names the remediation (set the file backend), matching the ADR restriction, and never touch the recovery envelope.

## Notes

Status stays custody-agnostic because it is a read-only inspection, per the ADR list, which scopes the file-only restriction to create/rotate/verify/recover and passphrase change.
