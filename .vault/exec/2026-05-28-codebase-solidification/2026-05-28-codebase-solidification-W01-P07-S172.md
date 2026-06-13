---
step_id: S172
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P07.S172 — real-behavior tests for CLASSIFIED_BY_MANUAL

## Outcome

Extended `src/aeat/application/ledger/test_models.py` with two real-behavior
tests that verify the constant and its cross-surface identity.

## Tests added

- `test_classified_by_manual_constant_value` — asserts
  `CLASSIFIED_BY_MANUAL == "manual"` against the specification value.
- `test_classified_by_manual_is_same_object_from_public_and_private_surfaces` —
  asserts `CLASSIFIED_BY_MANUAL is _CLASSIFIED_BY_MANUAL_FROM_MODELS`,
  proving the `__init__` re-export and the `_models` source are the same object.

## Verification

`uv run --no-sync pytest src/aeat/application/ledger/test_models.py -xvs` — 10 passed (8 pre-existing + 2 new).
