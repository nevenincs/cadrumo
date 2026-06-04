---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S211]]'
---

# `secure-storage-production-hardening` `W12.P26.S211` Review

## S211-001 | PASS | Testing registry helper is manifest-discovery only

`_testing_registry.py` builds filing drafts through
`build_runtime_schema_provider()` and `build_draft()`, which resolve bundled
registry snapshot metadata. It does not read or write local files, construct
storage repositories, derive SQL routes, inspect active sessions, or access
settings/environment state directly.

## S211-002 | PASS | Approval helper avoids storage defaults intentionally

When an approved draft is requested, the helper calls `approve_draft()` with an
explicit empty `TransactionCatalogue`. This keeps test fixtures deterministic
and prevents the helper from using the default transaction repository or active
bucket secure-object runtime.

## S211-003 | PASS | Existing helper tests cover the boundary

`test_testing_registry.py` covers registry-backed draft construction,
application approval stamping, non-approved approval-field clearing,
unsupported modelo refusal, duplicate input refusal, registry-projected sorted
values, deterministic draft ids, and decimal coercion rejection.

## S211-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/filing/_testing_registry.py src/aeat/application/filing/test_testing_registry.py` passed.
- `uv run --no-sync pytest src/aeat/application/filing/test_testing_registry.py -q` passed with 11 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S211
slice.

Disposition: close `AFR-109` as `manifest-discovery`.
