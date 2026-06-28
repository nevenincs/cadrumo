---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S265]]'
---

# `secure-storage-production-hardening` `W12.P26.S265` Review

## S265-001 | HIGH | Cross-store integrity errors leaked raw profile identifiers

`src/aeat/application/user_profile/_integrity.py` raised `ProfileIntegrityError` messages containing raw profile IDs and disagreeing physical-store values. Integrity failures are likely to be routed to repair diagnostics and logs, so the rendered message was too specific for a secure-storage boundary.

Disposition: fixed. The error text is now stable and sanitized, with the concrete mismatch category carried in structured context.

## S265-002 | MEDIUM | Integrity failures were not enrolled in localization

The integrity gate raised correctly typed AEAT exceptions, but those exceptions used ad hoc English strings instead of locale keys.

Disposition: fixed. Identity and lifecycle mismatch errors now use `application.user_profile.errors.profile_integrity_identity_mismatch` and `application.user_profile.errors.profile_integrity_status_mismatch`.

## S265-003 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/user_profile/_integrity.py src/aeat/application/user_profile/test_aggregate.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_aggregate.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

Disposition: close `AFR-163`.
