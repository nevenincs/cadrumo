---
tags:
  - "#exec"
  - "#calc-engine-grounding-swarm"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S04
related:
  - "[[2026-05-16-calc-engine-grounding-swarm-audit]]"
---

# calc-engine-grounding-restoration S04 — HIGH-1: modelo compare delta_rows no provenance

## Finding

Task #566 HIGH-1. `modelo_compare` CLI built `delta_rows` with no
`formula_id`, `legal_refs`, or `source_refs`. The typed `CasillaObservation`
envelope stored on `CalculationRevision.observations` was not consulted — only
the flat `casilla_values` mapping was read for values.

## Surface

`src/aeat/entrypoints/cli/_modelo.py` — `modelo_compare` command.

## Fix

Added `obs_by_id` dict built from both revisions' `observations` tuples
(year_b preferred, year_a fallback). Each `delta_rows` entry now includes
`formula_id`, `legal_refs`, `source_refs` looked up from `obs_by_id` for
the row's `casilla_id`, defaulting to `None`/`[]` when the casilla has no
typed observation (pre-existing revision with empty observations tuple).

## Test

`test_compare_delta_rows_carry_provenance` in
`src/aeat/entrypoints/cli/test_modelo_compare.py` — uses live M130 2026
registry engine to produce real `CasillaObservation` objects; simulates the
`obs_by_id` lookup; asserts computed casillas 03, 07, 19 carry non-empty
`formula_id`, `legal_refs`, `source_refs`; input casilla 01 has
`formula_id=None`.

## Commit

`8f01c536f` — `grounding(HIGH-1): surface formula_id/legal_refs/source_refs in modelo compare delta_rows`

## Status

Closed.
