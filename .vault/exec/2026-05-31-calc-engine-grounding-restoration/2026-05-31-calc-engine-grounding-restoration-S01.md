---
tags:
  - "#exec"
  - "#calc-engine-grounding-swarm"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S01
related:
  - "[[2026-05-16-calc-engine-grounding-swarm-audit]]"
---

# calc-engine-grounding-restoration S01 — CRIT-1: modelo_project casilla_observations

## Finding

Audit: `2026-05-16-calc-engine-grounding-swarm-audit` F2 / task #566 CRIT-1.

`modelo_project` CLI emitted `casilla_values` (flat dict) with no typed
`casilla_observations` list, so `formula_id`, `legal_refs`, `source_refs` were
invisible to JSON consumers despite being present on `RegistryCalculationEntry`.

## Surface

`src/aeat/entrypoints/cli/_modelo.py` — `modelo_project` command.

## Fix

Added `casilla_observations` list built from `engine_result.entries`, each entry
carrying `casilla_id`, `value`, `formula_id`, `legal_refs`, `source_refs`. The
list is included in the `payload` dict alongside the existing flat
`casilla_values`.

## Test

`test_proyecto_casilla_observations_carry_provenance` in
`src/aeat/entrypoints/cli/test_modelo_projection.py` — uses live M130 2026
registry engine; asserts computed casillas 03 and 19 carry non-empty
`formula_id`, `legal_refs`, `source_refs`; input casilla 01 has
`formula_id=None`.

## Commit

`964e179b0` — `grounding(CRIT-1): add casilla_observations provenance to modelo project payload`

## Status

Closed.
