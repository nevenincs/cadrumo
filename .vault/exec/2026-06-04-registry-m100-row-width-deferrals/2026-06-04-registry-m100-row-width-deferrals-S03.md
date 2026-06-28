---
tags:
  - '#exec'
  - '#registry-m100-row-width-deferrals'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S03'
related:
  - '[[2026-06-04-registry-m100-row-width-deferrals-plan]]'
---

# S03 M100 2020 Constraints Table Formatting

Scope: convert the M100 2020 inline `constraints` row to an equivalent nested TOML table.

## Description

- Replaced the inline `constraints = { ... }` table in `100/revisions/2020/casillas/0146-0153.toml` with `[revisions."2020".casillas.constraints]`.
- Preserved `sign`, every `legal_refs` id, every `source_refs` id, and original ordering.
- Left the casilla's top-level `legal_refs` and `source_refs` fields unchanged.

## Outcome

- Parsed TOML equality against `HEAD` passed.
- Loaded M100 equality against a temporary `HEAD` copy passed.
- Post-S03 row inventory reports the widest registry TOML row at 528 characters.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_reviewability_baseline_remains_well_below_hard_cap -q` passed: 2 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q` passed: 41 passed.

## Notes

- This was a TOML shape change only; loader equality proved the compiled registry object is unchanged.
