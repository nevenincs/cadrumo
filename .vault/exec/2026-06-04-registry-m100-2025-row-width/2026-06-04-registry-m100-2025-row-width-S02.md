---
tags:
  - '#exec'
  - '#registry-m100-2025-row-width'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S02'
related:
  - '[[2026-06-04-registry-m100-2025-row-width-plan]]'
---

# S02 M100 2025 Legal-Refs Formatting

Scope: wrap the four M100 2025 `legal_refs` rows above 520 characters without changing TOML values.

## Description

- Wrapped `legal_refs` arrays in M100 2025 casillas 0549, 0553, 0562, and 0563.
- Preserved every legal reference id and original ordering.
- Left source references, formulas, labels, sections, and semantic roles unchanged.

## Outcome

- Parsed TOML equality against `HEAD` passed for all four files.
- Loaded M100 equality against a temporary `HEAD` copy passed.
- Post-S02 row inventory reports the widest registry TOML row at 517 characters.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_reviewability_baseline_remains_well_below_hard_cap -q` passed: 2 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q` passed: 41 passed.

## Notes

- The current widest row moved to M200, outside this M100 2025 slice.
