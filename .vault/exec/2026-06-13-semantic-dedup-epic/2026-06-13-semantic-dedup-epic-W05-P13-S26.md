---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S26'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C1-1a Redirect the two named sha256-hex helper redeclarations to core.hashing.sha256_hex

## Scope

- `src/aeat/adapters/persistence/storage/sql/_secure_object_crypto.py`

## Description

- Re-verified at HEAD: `sql/_secure_object_crypto.sha256_hex` (a byte-identical
  same-name re-declaration) and `calc_sheets/_workbook_export._sha256`.
- `_secure_object_crypto` now imports `sha256_hex` from core for its
  `derive_revision_id` use; `secure_objects.py` imports `sha256_hex` from core
  directly (rather than re-exporting through `_secure_object_crypto`).
- `_workbook_export` consumes `sha256_hex` at both call sites; dropped the local
  `_sha256` def and the unused `hashlib` import.

## Outcome

Committed as `c94f0c4dd`, tagged `relocation:sha256_hex`. Ruff clean; 242
storage/calc_sheets tests green incl. secure-object roundtrips and revision-id
derivation. No public shape change.

## Notes

Routed the `secure_objects` consumer to core directly to avoid leaving a
re-export shim in `_secure_object_crypto`.
