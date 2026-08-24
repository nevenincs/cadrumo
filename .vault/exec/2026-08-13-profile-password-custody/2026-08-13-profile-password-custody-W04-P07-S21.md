---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:331148e589285496d47646825671e88bdc930b1952cc3d63e1ec45c1620180b8'
step_id: 'S21'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium perform a negative architecture audit proving only an existence-only retired-path detector remains and no legacy custody route is reachable

## Scope

- `src/cadrumo/`

## Description

Audit the negative custody architecture against the hard-cutover boundaries, verify the absence gates and ownership split, and correct the two stale prose references found by the audit.

## Outcome

PROVEN on all four axes at HEAD: (1) every legacy/retired/shared-master/provider token resolves to a deliberate refusal or detection site with a live consumer (the existence-only detector in `_capsule_discovery.py` with its LEGACY_CUSTODY_DETECTED refusal, the recognition-only manifest name, the retired product-DB filename refusal, the former-product namespace refusal, the provider protocol's unsecured-only fencing); (2) the hard-cutover absence gate is green (12 passed) and its five declared open violations match the live reach sites exactly; (3) none of the eight deleted storage surfaces exists on disk and no production module imports any of them; (4) the two-package split is the documented end state with a single facade cross-import (the S28 wipe relocation). Two LOW nits fixed in the same commit: the gate's stale docstring narrative (the observation store, Clave Movil client and readiness-check reaches it named have moved onto the capsule surface; only the Google OAuth tax-id helper remains outside the root) and the dangling `:mod:` reference to the deleted `_manifest_io` in `bucket/tests/test_bucket_errors.py`.

## Notes

Closes clean — no defect blocks the cutover claim. The remaining LOW nit (a local `provider` variable name at `_profile_pointer_transaction.py:154`) is naming-only and recorded rather than chased.
