---
tags:
  - '#exec'
  - '#core-authority'
step_id: S88
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W10.P26.S88 - validate_identity NIF rejection regression tests

## Outcome

Added `TestNifHardeningRejection` class to `core/identity/test_documents.py` with
three regression tests proving `validate_identity` rejects malformed NIFs that a bare
`strip().upper()` normaliser would silently accept:

1. `test_wrong_check_letter_rejected_not_silently_normalised` — `12345678A` (correct check is Z)
   raises `IdentityError` with `errors.identity.nif_check_letter_mismatch`.

2. `test_short_nif_rejected_not_silently_normalised` — `1234567Z` (7 digits, wrong shape)
   raises `IdentityError` with `errors.identity.nif_invalid_shape`.

3. `test_uppercase_garbage_rejected_not_silently_normalised` — `NOTANIF` raises `IdentityError`.

The production `validate_identity` function in `core/identity/_documents.py` already
implements full check-letter validation and requires no code changes. The "hardening"
is the regression-test gate pinning this contract.

The `_normalise_tax_identity` in `application/auth/_sessions.py` serves a different
semantic role (loose identity comparison, not strict parse-and-validate). Replacing
its behavior with `validate_identity` would break the soft-fail comparison path and
is deferred pending a scoped ADR amendment.

## Commit

`8588b80d2` — test(identity): W10.P26.S88 - regression tests for validate_identity NIF rejection

## Files touched

- `src/aeat/core/identity/test_documents.py` — added TestNifHardeningRejection (30 lines)

## Verification

All 37 tests in `test_documents.py` pass.
