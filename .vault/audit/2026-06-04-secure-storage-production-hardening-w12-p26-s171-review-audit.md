---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:c57bd71b7ca6d6844c1be13f5e539a3858f9e0fc8b05bdc7927d90a0c02f0b36'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S171` Review

## S171-001 | PASS | Master-key package facade does not acquire custody

The retired module re-exports the master-key provider hierarchy, active-session entry point, KDF parameter model, secure atomic write helper, and recovery primitives. The facade does not call `get_master_key_provider`, `get_master_key`, `provision_master_key`, `activate_master_key_provider`, `atomic_write_secure_bytes`, or any recovery unwrap/write helper at import time.

The `bootstrap-custody` classification remains accurate because the exported objects include custody-bearing provider and recovery APIs. The implementation risk is owned by later rows for `_active_session.py`, `_bucket_session.py`, `_dek_wrap.py`, `_kdf.py`, `_master_key.py`, `_recovery.py`, and `_recovery_facade.py`.

## S171-002 | PASS | No direct settings or environment wrangling in the facade

The facade has no direct settings construction, `load_settings` call, naked environment access, keyring import, file open, read/write, SQL route, or logging behavior. Importing `_active_session` registers that module's atexit cleanup hook; the hook belongs to `AFR-070` / `W12.P26.S172`, not this package facade row.

## S171-003 | PASS | Direct tests stay behavioral

The scoped tests exercise real `EphemeralMasterKeyProvider` re-entrant behavior, error-registry binding, structured error envelope round-trips, and subtype relationships for master-key cluster errors. They do not introduce fake/stub classes, mocks, monkeypatching, skip, or xfail shortcuts.

Validation:

- the historical check passed with 12 tests.
- the historical check passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Touched-surface hygiene scan found no direct environment access, settings construction, key acquisition calls, keyring calls, file I/O calls, broad exception suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, or direct output.

Review-agent note: a reviewer subagent was unavailable in this session due the current usage limit, so the supervisor completed the same checklist locally.

Disposition: close `AFR-069` as `bootstrap-custody` facade metadata.
