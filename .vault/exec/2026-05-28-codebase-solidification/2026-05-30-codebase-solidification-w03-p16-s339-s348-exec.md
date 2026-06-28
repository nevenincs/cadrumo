---
step_id: S339-S348
feature: codebase-solidification
phase: P16
wave: W03
date: 2026-05-30
modified: '2026-05-30'
agent: coder-delta7
commit: bea5a414f
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W03.P16 — UTC validator enrollment sweep S339-S348

## Collision check

`git diff` on all nine target files returned no output — no non-authored WIP.

## Steps executed

- **S339** `bucket/_export_header.py`: deleted local `_ensure_utc`, imported `_validate_utc_aware`; call-site in `_check_created_at` wraps via `try/except CoreValidationError → BucketValidationError`.
- **S340** `envelope/_envelope.py`: two `_require_aware` validators on `Envelope` and `CipherEnvelope` — inline guards replaced with `_validate_utc_aware` wrapper → `StorageValidationError`.
- **S341** `secret_store/_secret_store.py`: `SecretRecord._require_aware` — inline guard replaced with `_validate_utc_aware` wrapper → `StorageValidationError`.
- **S342** `application/review/_models.py`: `_ReviewItemBase._require_aware` — bare `ValueError` migrated; `_validate_utc_aware` called directly (inherits `ValueError`).
- **S343** `domain/transactions/_raw_transaction.py`: `RawProvenance._require_aware_timestamp` — inline guard replaced with `_validate_utc_aware` wrapper → `TransactionValidationError`.
- **S344** `domain/transactions/_models.py`: `_require_aware_datetime` helper — inline guard replaced with `_validate_utc_aware` wrapper → `TransactionValidationError`.
- **S345** `core/corpus_manifest/__init__.py`: `CorpusManifest._require_aware` — inline guard replaced with `_validate_utc_aware` wrapper → `CorpusManifestError`.
- **S346** `core/observability/_models.py`: `_require_tz_aware` helper — single `tzinfo is None` check replaced with `_validate_utc_aware` delegation.
- **S347** `application/auth/_acquisition_lock.py`: deleted local `_utc` coerce function; call-site now uses `_coerce_utc_aware` with explicit `None` guard at the call-site.
- **S348** `src/aeat/test_utc_validator_enrollment_inventory.py`: new inventory test using `ast.walk` — asserts zero `tzinfo is None` comparisons survive in production code outside `aeat.core.time._utc`.

## Additional sites migrated (discovered by S348 test)

Eight additional files had inline tzinfo guards not listed in the original nine:
- `adapters/outbound/aeat/auth/_authenticator.py` — coerce via `_coerce_utc_aware`
- `adapters/outbound/aeat/auth/certificate.py` — two coerce sites (already imported `_coerce_utc_aware`)
- `adapters/outbound/aeat/browser/_site_health_parsers.py` — two coerce sites via `_coerce_utc_aware`
- `adapters/outbound/google/_calc_sheets_pull.py` — coerce site via `_coerce_utc_aware`
- `application/auth/_sessions.py` — validate site, `_validate_utc_aware` direct call
- `application/ledger/_actions.py` — `_normalise_timestamp` coerce helper, delegated to `_coerce_utc_aware`
- `application/storage/calc_sheets/_records.py` — model validator, `_validate_utc_aware` direct call; unused `UTC` import cleaned up
- `domain/attachments/_models.py` — validate with wrapper → `AttachmentValidationError`

## Test outcome

- Inventory test: **1 passed**
- Domain tests (transactions, attachments, bucket, envelope, secret_store): **143 passed**, 2 pre-existing failures (attachment repo byte scan, namespace registry) unrelated to UTC changes.

## Commit

`bea5a414f` — `utc-validator(P16): enroll all production sites in _validate_utc_aware (S339-S348)`
