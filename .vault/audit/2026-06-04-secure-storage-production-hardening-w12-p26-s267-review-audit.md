---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S267]]'
---

# `secure-storage-production-hardening` `W12.P26.S267` Review

## S267-001 | PASS | Lifecycle exceptions use stable translated surfaces

`ProfileLifecycleService` raises the domain user-profile exceptions for duplicate, tombstoned, and schema-validation refusals. User-facing strings now stay stable and translated through `translated_message`; raw profile and bucket identifiers are kept in exception context rather than rendered in `str(error)`.

## S267-002 | PASS | Event payloads are intentional encrypted audit data

Lifecycle events persist through `BucketEventHistoryRepository`, whose namespace is registered as `aeat.domain.buckets.event_history` with `FINANCIAL` sensitivity and profile-local scope. The event payload can carry operator labels and source profile identifiers for audit reconstruction, but it is routed through `SecureObjectRepository` and the encrypted `SecureObjectRow.payload` column.

## S267-003 | PASS | Test coverage proves the privacy boundary without mocks

The lifecycle tests cover translated exception keys, sanitized rendered errors, and the encrypted event-history boundary. The new storage test provisions a real active bucket, emits register/rename/duplicate lifecycle events, confirms decrypted event payloads preserve the intended audit values, then scans the SQLite database bytes to prove those profile ids and labels are not present as plaintext.

## S267-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/user_profile/_lifecycle.py src/aeat/application/user_profile/test_lifecycle.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_lifecycle.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

Disposition: close `AFR-165`.
