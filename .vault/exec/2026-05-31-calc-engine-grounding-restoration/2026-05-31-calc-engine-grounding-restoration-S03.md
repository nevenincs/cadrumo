---
tags:
  - "#exec"
  - "#calc-engine-grounding-swarm"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S03
related:
  - "[[2026-05-16-calc-engine-grounding-swarm-audit]]"
---

# calc-engine-grounding-restoration S03 — CRIT-3: RegistryFiledStateDrift discards provenance

## Finding

Audit: `2026-05-16-calc-engine-grounding-swarm-audit` / task #566 CRIT-3.

`RegistryFiledStateDrift` had no `formula_id`, `legal_refs`, or `source_refs` fields.
`compare_calculation_to_filed_observation` discarded the regulatory grounding from
`RegistryCalculationEntry` when building drift entries, so an operator auditing a
comparison result could not determine which BOE article authorised the drifted formula.

## Surface

`src/aeat/domain/calculations/registry/_filed_state.py`.

## Fix

Added three optional provenance fields to `RegistryFiledStateDrift`:
- `formula_id: str | None = None`
- `legal_refs: tuple[str, ...] = ()`
- `source_refs: tuple[str, ...] = ()`

Updated `compare_calculation_to_filed_observation` to build
`entries_by_target = {entry.target: entry for entry in calculation.entries}` and
populate provenance on each drift from the matching entry (defaulting to
`None`/`()` for non-computed casillas).

## Test

`test_filed_state_drift_carries_formula_provenance` in
`src/aeat/domain/calculations/registry/test_filed_state.py` — uses live M130 2026
registry; drifts computed casilla "19" by 0.01; asserts `drift.formula_id is not None`,
`len(drift.legal_refs) > 0`, `len(drift.source_refs) > 0`.

## Commit

`934d9b6d8` — `grounding(CRIT-3): surface provenance on RegistryFiledStateDrift`

## Status

Closed.
