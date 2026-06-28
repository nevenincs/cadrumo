---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---

# `calculation-truth-registry` `Phase 0B` `previous-filing-period-chain`

Extended previous-filing binding resolution to multi-period annual dependency chains.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/test_formula_runtime.py`

## Description

Previous-filing selectors now support either a single `period` or multiple `source_periods`. The observation requirement builder expands multi-period selectors into concrete filed-declaration requirements, and the resolver aggregates observed casilla values across every required period.

This makes Modelo 180 annual summary bindings consume the required Modelo 115 quarterly observations through the central registry layer instead of caller-assembled relation inputs.

## Tests

Verified behavior with `uv run pytest src\aeat\domain\calculations\registry\test_formula_runtime.py -q`.

Verified focused style and typing with `uv run ruff check` and `uv run ty check` on touched Python surfaces.
