---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S176]]'
---

# `secure-storage-production-hardening` `W12.P26.S176` Review

## S176-001 | PASS | KDF errors stay inside AEAT exceptions

`derive_kek` rejects unsupported manifest algorithms and output lengths with `KeyDerivationError` bound to `errors.integrity.integrity_storage_key_derivation`. The wrapper also converts argon2-cffi, type, and value failures into the same AEAT storage exception family with the original cause chained for diagnostics.

## S176-002 | PASS | Cryptographic behavior remains grounded

The accepted path still delegates to `argon2.low_level.hash_secret_raw` with `Type.ID`, the manifest-provided salt and costs, and a 32-byte output length. The known-answer vector remains upstream-library output rather than a reimplementation of the KDF in tests.

## S176-003 | PASS | Tests avoid shortcuts and leakage

The focused tests cover the upstream Argon2id known-answer vector, output length, salt variance, passphrase variance, unsupported algorithm refusal, unsupported output-length refusal, registry binding, envelope construction, localized translated message keys, and passphrase non-disclosure in the rendered error envelope. They do not use fake/stub classes, mocks, monkeypatching, skip, or xfail shortcuts.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_kdf.py src/aeat/adapters/persistence/storage/master_key/test_kdf_errors.py src/aeat/adapters/persistence/storage/master_key/test_kdf_params.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py::test_profile_repository_kdf_defaults_flow_from_canonical_master_key_model` passed with 20 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_kdf.py src/aeat/adapters/persistence/storage/master_key/test_kdf.py src/aeat/adapters/persistence/storage/master_key/test_kdf_errors.py src/aeat/adapters/persistence/storage/master_key/test_kdf_params.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- Touched-surface hygiene scan found no broad exception suppressions, direct settings construction, naked environment access, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, or naked encoding literals.

Review-agent note: spawning `vaultspec-code-reviewer` remains unavailable in this session due the agent thread limit, so the supervisor completed the same checklist locally.

Disposition: close `AFR-074` as `bootstrap-custody`.
