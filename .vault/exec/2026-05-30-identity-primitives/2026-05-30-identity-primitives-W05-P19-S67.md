---
step_id: S67
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
  - '[[2026-05-30-identity-primitives-reference]]'
---

# identity-primitives W05.P19.S67 — _HEX_*_LENGTH misplacement detector

## Scope

Land the third ADR Rule 9 detector: assert no
`_HEX_<name>_LENGTH` constant is declared outside the owning
`_ids.py` module. W03.P10 collapsed the historical violators
(`_HEX_TRANSACTION_ID_LENGTH`, `_HEX_INVOICE_ID_LENGTH`,
`_HEX_WORK_UNIT_ID_LENGTH`); the detector locks the result.

## Outcome

Extended `_identity_placement.py` with
`find_misplaced_hex_length_constants` which walks each
module-level `Assign` / `AnnAssign` target, matches the name
against `^_HEX_[A-Z0-9_]+_LENGTH$`, and skips `_ids.py`
modules. Added `test_no_misplaced_hex_length_constants`.

## Verification

`uv run --no-sync pytest
src/aeat/diagnostics/test_identity_primitive_placement.py`
runs the three landed detectors (3 passed, 4.71s); no
misplaced shape constants surfaced.
