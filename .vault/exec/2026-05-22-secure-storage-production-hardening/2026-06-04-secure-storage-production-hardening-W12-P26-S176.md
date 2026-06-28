---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S176'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s176-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S176`

Closed `AFR-074` for Argon2id KEK derivation.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/master_key/_kdf.py` against the `master-key` scanner signal and `bootstrap-custody` target.
- Added a local `KeyDerivationError` factory that binds KDF failures to `errors.integrity.integrity_storage_key_derivation`.
- Converted argon2-cffi, type, and value failures into `KeyDerivationError` so third-party exceptions do not escape the storage boundary.
- Preserved the existing Argon2id algorithm, OWASP baseline parameters, manifest-side parameter consumption, and 32-byte KEK output.
- Updated real-behavior tests to assert translated key-derivation failures and redacted envelope output.

## Outcome

`AFR-074` is closed as a `bootstrap-custody` KDF implementation row.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_kdf.py src/aeat/adapters/persistence/storage/master_key/test_kdf_errors.py src/aeat/adapters/persistence/storage/master_key/test_kdf_params.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py::test_profile_repository_kdf_defaults_flow_from_canonical_master_key_model`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_kdf.py src/aeat/adapters/persistence/storage/master_key/test_kdf.py src/aeat/adapters/persistence/storage/master_key/test_kdf_errors.py src/aeat/adapters/persistence/storage/master_key/test_kdf_params.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-surface hygiene scan found no broad exception suppressions, direct settings construction, naked environment access, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, or naked encoding literals.

## Notes

`ManifestKdfParams` already rejects malformed salts before `derive_kek` runs, so this step did not add test-only mutation to force argon2 failures. The hardening keeps realistic manifest rejection paths covered and narrows the runtime boundary for adverse argon2 failures.
