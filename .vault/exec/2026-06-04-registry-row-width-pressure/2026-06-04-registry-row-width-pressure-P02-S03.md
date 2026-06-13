---
tags:
  - '#exec'
  - '#registry-row-width-pressure'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S03'
related:
  - '[[2026-06-04-registry-row-width-pressure-plan]]'
---

# P02.S03 Non-M100 Row-Width Formatting

Scope: `P02.S03` reformatted clean non-M100 TOML rows authorised by the row-width inventory.

## Description

- Wrapped the long `formulas` array in `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/constructs/0001-modelo-202-foundation.toml`.
- Wrapped the long `formulas` array in `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`.
- Preserved every formula id and its original ordering.
- Left all remaining near-threshold rows for M100-specific handling or deferral.

## Outcome

- Parsed TOML equality against `HEAD` passed for both touched files.
- Loaded modelo equality against temporary `HEAD` copies passed for M202 and M303.
- Post-S03 row inventory found no non-M100 registry TOML rows at or above 540 characters.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q` passed: 41 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q` passed: 27 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_reviewability_baseline_remains_well_below_hard_cap -q` passed: 2 passed.

## Notes

- Remaining rows at or above 540 characters after this step are M100 rows only: four completeness `legal_refs` rows and one inline `constraints` row.
- Full `test_registry_reviewability.py` remains unsafe to treat as this step's gate while unrelated concurrent edits to `src/aeat/domain/calculations/registry/_validate_relation_periods.py` keep its module-size assertion red.
