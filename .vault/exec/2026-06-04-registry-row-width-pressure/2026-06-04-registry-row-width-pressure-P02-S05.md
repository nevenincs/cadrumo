---
tags:
  - '#exec'
  - '#registry-row-width-pressure'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S05'
related:
  - '[[2026-06-04-registry-row-width-pressure-plan]]'
---

# P02.S05 Row-Width Baseline Tightening

Scope: `P02.S05` tightens the registry TOML row-width baseline to match the post-format corpus.

## Description

- Lowered `_MAX_BASELINE_TOML_LINE_CHARS` from 575 to 555 in `test_registry_reviewability.py`.
- Chose 555 because the post-S04 audited maximum registry TOML row length is 552 characters.
- Left the hard cap unchanged at 600 characters.

## Outcome

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_registry_reviewability.py` passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_reviewability_baseline_remains_well_below_hard_cap -q` passed: 2 passed.
- Full `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q` failed only in `test_registry_validator_modules_stay_below_p05_reviewability_baseline` because unrelated concurrent edits leave `_validate_relation_periods.py` at 217 lines against the existing 203-line ceiling.

## Notes

- S05 does not adjust validator-module baselines; that would mix this TOML row-width gate with unrelated validator-module work.
