---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S340-001 | FIXED | Filing runtime bucket refusal lacked structured context

`src/aeat/domain/filing/_runtime_repository.py` already raised the correct project
exception with a locale key for missing bucket state, but it did not distinguish a blank
explicit bucket id from a missing active profile bucket. Both branches now include a
small structured `reason` context so CLI/error-envelope consumers can diagnose the route
failure without parsing message text.

## S340-002 | PASS | Runtime construction stays centralized

`secure_objects_for_filing_bucket()` still delegates to the storage runtime repository
factory for the selected bucket. The helper does not construct SQL engines directly and
the focused unready-runtime test proves it refuses when the active runtime/session route
is not available.

## S340-003 | PASS | Exceptions and localization follow project conventions

The helper continues to raise `ModeloDraftError`, which derives from the core
`AeatError` hierarchy, and it continues to carry the existing
`application.workflow.errors.no_active_profile_bucket` locale key. No locale catalogue
changes were needed; `python -m aeat.locales audit` passed.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/filing/_runtime_repository.py src/aeat/domain/filing/test_runtime_repository.py src/aeat/domain/filing/_repository.py src/aeat/domain/filing/_complementaria_repository.py`
- `uv run --no-sync pytest -q src/aeat/domain/filing/test_runtime_repository.py src/aeat/domain/filing/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_amendment_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "resolve_filing_repository_bucket_id secure_objects_for_filing_bucket active profile bucket StorageValidationError runtime route ModeloDraftError context" --type code --port 8766 --max-results 8`
