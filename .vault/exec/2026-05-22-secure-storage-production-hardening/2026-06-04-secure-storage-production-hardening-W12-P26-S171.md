---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S171'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s171-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S171`

Closed `AFR-069` for the master-key package facade.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/master_key/__init__.py` against the `master-key` scanner signal and `bootstrap-custody` target.
- Confirmed the facade only re-exports provider, active-session, KDF parameter, secure-write, and recovery primitives.
- Confirmed the facade does not acquire key material, activate providers, resolve settings, read environment variables, call keyring, open files, open SQL routes, or write recovery/master-key artifacts.
- Recorded that implementation-bearing behavior remains assigned to the subsequent master-key rows.
- Validated scoped master-key error-envelope tests and ruff.
- Closed `S171` through `vaultspec-core vault plan step check` and updated `AFR-069` to closed.

## Outcome

`AFR-069` is closed as `bootstrap-custody` facade metadata.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py src/aeat/adapters/persistence/storage/master_key/test_cluster_envelopes.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/__init__.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py src/aeat/adapters/persistence/storage/master_key/test_cluster_envelopes.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-surface hygiene scan found no direct environment access, settings construction, key acquisition calls, keyring calls, file I/O calls, broad exception suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, or direct output.

## Notes

No source change was required for this row. The `bootstrap-custody` implementation risks remain in the following master-key module rows, starting with `AFR-070` / `W12.P26.S172`.
