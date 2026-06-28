---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S01'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W01.P01.S01`

Removed lazy master-key minting from provider read paths and introduced
explicit provisioning methods for enrollment.

- Modified: `src/aeat/adapters/persistence/storage/master_key/_master_key.py`
- Modified: `src/aeat/adapters/persistence/storage/master_key/test_master_key.py`

## Description

`KeyringMasterKeyProvider.get_master_key` now refuses absent key material with
typed missing-material errors instead of minting into the OS keychain. Explicit
enrollment uses `provision_master_key`.

`FileFallbackMasterKeyProvider.get_master_key` now refuses absent file-fallback
material instead of calling the private mint path. Explicit enrollment uses
`provision_master_key`, which serializes provisioning under the existing lock,
refuses existing complete state by default, and refuses torn state.

Factory behavior was adjusted so explicit keyring selection probes backend
availability without implicitly creating material, and auto mode returns an
unprovisioned keyring provider when no fallback material exists.

## Tests

Ran focused provider tests:

`uv run --no-sync pytest src/aeat/adapters/persistence/storage/master_key/test_master_key.py -q`

Result: 51 passed, 1 skipped.
