---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-10-03'
body_hash: 'sha256:2c64ae05791416e9220647d271c7020b0bf734257760d488a298b273b0b893ca'
related: []
---

# `secure-storage-production-hardening` Code Review

## S340-001 | FIXED | Filing runtime bucket refusal lacked structured context

The retired module already raised the correct project
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

- the historical check
- the historical check
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "resolve_filing_repository_bucket_id secure_objects_for_filing_bucket active profile bucket StorageValidationError runtime route ModeloDraftError context" --type code --port 8766 --max-results 8`
