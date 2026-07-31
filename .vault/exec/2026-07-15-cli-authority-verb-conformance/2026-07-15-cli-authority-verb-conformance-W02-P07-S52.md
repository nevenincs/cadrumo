---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:388d50ebfb43576051119057285d20ee8af7e0a9bbe5f7f099abefd5e0c5310a'
step_id: 'S52'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove register, select, check, status, test, and login consume the same resolved certificate bytes

## Scope

- `src/cadrumo/application/auth/tests/test_certificate_sources_check.py`

## Description

- Confirm register, select, check, status, test, and login all consume the same resolved certificate bytes and the same secure-storage secret.
- Confirm a selected named source with no bound secret fails closed (resolves `password=None`) and never inherits an unrelated global Settings password across the resolver, central provider factory, status, test, preflight, and login surfaces.
- Confirm renewing the selected source and cross-bucket / cross-root routing keep every consuming surface on the same resolved bytes.

## Outcome

Verified complete against the committed tree. `test_certificate_sources_check.py` proves the active-credential resolver, `check`, `auth status`, `auth test`, the central provider factory, live preflight, and `login` all agree on the selected source's path and secure-storage secret, with a deliberately-wrong global password unable to open a named source and a secretless named source failing closed. The file is green in the focused run (part of the 99-passed application-auth suite).

## Notes

The shared-resolution parity proofs landed in the W02.P07 credential-unification wave (commits `f5273bda59`, `84c435bb94`, and the in-flight freeze snapshots); this step is closed as verified-complete with its real-behavior parity and fail-closed gates green.
