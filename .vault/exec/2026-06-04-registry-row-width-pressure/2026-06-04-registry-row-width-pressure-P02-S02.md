---
tags:
  - '#exec'
  - '#registry-row-width-pressure'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S02'
related:
  - '[[2026-06-04-registry-row-width-pressure-plan]]'
---

# `registry-row-width-pressure` `P02.S02` format

Scope: reformat clean near-threshold M100 casilla TOML rows without changing
TOML values.

## Description

- Reformatted `legal_refs` arrays for M100 2025 casillas `0550` and `0552`
  from single-line arrays to multiline arrays.
- Preserved reference order and values.
- Compared loaded M100 `ModeloDefinition` output before and after using a
  temporary copy reconstructed from `HEAD`.

## Outcome

S02 completed. The maximum committed TOML row width dropped from 572
characters to 552 characters.

## Notes

Verification:

- M100 `load_modelo_directory` equality before/after: passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_reviewability_baseline_remains_well_below_hard_cap -q` passed: 2 tests.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q` passed: 41 tests.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q` passed: 27 tests.

The full `test_registry_reviewability.py` file currently fails outside this
step because concurrent dirty docstring work grew
`_validate_relation_periods.py` beyond its module-line baseline. This step did
not touch that file.
