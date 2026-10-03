---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:92d1d3afa3c919fa0ccd8f8ef0278978e4235cf85905fc7037832aa869cb76d9'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S265` Review

## S265-001 | HIGH | Cross-store integrity errors leaked raw profile identifiers

The retired module raised `ProfileIntegrityError` messages containing raw profile IDs and disagreeing physical-store values. Integrity failures are likely to be routed to repair diagnostics and logs, so the rendered message was too specific for a secure-storage boundary.

Disposition: fixed. The error text is now stable and sanitized, with the concrete mismatch category carried in structured context.

## S265-002 | MEDIUM | Integrity failures were not enrolled in localization

The integrity gate raised correctly typed AEAT exceptions, but those exceptions used ad hoc English strings instead of locale keys.

Disposition: fixed. Identity and lifecycle mismatch errors now use `application.user_profile.errors.profile_integrity_identity_mismatch` and `application.user_profile.errors.profile_integrity_status_mismatch`.

## S265-003 | PASS | Validation

- the historical check
- the historical check
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

Disposition: close `AFR-163`.
