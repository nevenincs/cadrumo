---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S197]]'
---

# `secure-storage-production-hardening` `W12.P26.S197` Review

## S197-001 | PASS | Auth diagnostics stay active-profile runtime-bound

`src/aeat/application/auth/_diagnostics.py` retrieves encrypted diagnostics via
`secure_object_repository_for_active_bucket()`. It does not construct
`SecureObjectRepository` directly, read environment variables, or bypass the
storage runtime.

## S197-002 | PASS | Encoding constants are centralized

Diagnostic payload decode, updated-payload encode, redacted-reference hashing,
and focused test fixture payloads now use `UTF_8_ENCODING` instead of raw
encoding literals.

## S197-003 | PASS | Typed errors and redaction remain intact

Auth diagnostic validation errors derive from the core AEAT error hierarchy via
`CoreValidationError`. Redaction behavior remains unchanged: page bodies are not
returned, and sensitive references are exposed as existing SHA-256 fingerprints
or newly-derived fingerprints.

## S197-004 | PASS | Runtime-default coverage already guards the slice

The migrated runtime-default guard suite already includes `auth_diagnostics` for
missing-session and route/session-mismatch refusal. The S197 run re-executed the
focused `auth_diagnostics` cases after the encoding cleanup.

Validation:

- `uv run --no-sync ruff check src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_diagnostics.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/auth/test_diagnostics.py` passed with 5 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "migrated_runtime_defaults_refuse and auth_diagnostics"` passed with 2 selected tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Reviewer note: subagent review remains unavailable because the reviewer agent hit
the account usage limit earlier in this run. Host review found no remaining
critical, high, medium, or low findings in the S197 slice.

Disposition: close `AFR-095`.
