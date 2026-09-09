---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b9e6bc51324d3fed56057d417b853529ea3a9cb28b7b989a29a24c301c0daaa1'
step_id: 'S279'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only recipient-encryption strict-load and public-key projection APIs, their DTO/error/locale residue, and newly exposed parser helper; migrate meaningful tests to the live ensure owner and raw public-key field, preserve cryptographic behavior, update cadence, and remeasure exact reachability.

## Scope

- `recipient encryption module`
- `feedback prose/tests`
- `CLI tests`
- `error registry`
- `locales`

## Changes

- `M` `src/cadrumo/application/modelo/review_package_recipient_encryption.py`
- `M` `src/cadrumo/application/modelo/review_package_feedback.py`
- `M` recipient-encryption and feedback application/CLI tests
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `src/cadrumo/locales/{ca,en,es,hu}/application.yml`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact symbol/locale search -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` keypair security tests -> `6 passed, 22 deselected`
- `verify:` feedback application roundtrip tests -> `4 passed, 8 deselected`
- `verify:` focused CLI integration tests -> `3 passed, 7 unrelated readiness failures`
- `verify:` exact reachability -> `261 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

The live `ensure_recipient_encryption_keypair` owner already loads, validates, or mints the encrypted keypair, and consumers accept its `public_key_hex` directly. The removed strict-load and public-projection APIs had only tests. Their missing-before-mint error and locale were therefore nonexistent product behavior. The CLI failures occur earlier in a shared Modelo 111 package fixture that lacks the newly required concerted-school profile fact; three unaffected CLI cases pass and the application cryptographic roundtrip is green. Exact unused symbols improved from 263 to 261 after remeasurement exposed and removed the load-only payload parser.
