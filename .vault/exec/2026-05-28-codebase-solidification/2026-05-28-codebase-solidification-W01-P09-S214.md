---
step_id: S214
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-07-17'
body_hash: 'sha256:b7114d062445a620f6ea9fd10714789d0324b08ec082b2610885f3c364df0131'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P09.S214 — calculation grounding assertion test

## Outcome

Created `src/aeat/domain/calculations/test_calculation_grounding.py` with three tests:
- `test_tautology_gate_file_exists_and_is_non_vacuous`: gate has >=2 test functions.
- `test_chain_behaviour_suite_exists_as_gate_target`: scanned fixture file present.
- `test_tautology_gate_waiver_set_is_empty`: `_TAUTOLOGY_WAIVERS` is `frozenset()` (AnnAssign form).

All tests are structural assertions against the grounding gate; they fail loudly if
the gate is hollowed out (deletion, rename, or waiver addition).

## Files touched

- `src/aeat/domain/calculations/test_calculation_grounding.py` (new)

## Verification

`uv run --no-sync pytest src/aeat/domain/calculations/test_calculation_grounding.py -q` — 3 passed.
