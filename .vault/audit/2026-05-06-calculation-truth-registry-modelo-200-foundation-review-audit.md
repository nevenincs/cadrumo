---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-06-calculation-truth-registry-modelo-200-foundation-exec]]'
---



# `calculation-truth-registry` Code Review

REVIEW-001 | INFO | No findings
Reviewed the Modelo 200 foundation against the registry ADR and plan. The
implementation keeps calculation authority in TOML: legal references, source
references, official casillas, the Modelo 202 relation, and the final 00599
formula are all registry-owned. Python changes are limited to a behaviour test
that resolves real registry relations and evaluates the snapshot runtime.

Casilla 00599 uses the relation-resolved Modelo 202 aggregate directly, which
keeps the Modelo 200 casilla set aligned with official form identifiers.

Open scope remains explicit: full Modelo 200 layout transcription, export
layout, extraction profiles, live sanitized filed-data fixtures, and complete
legal correctness coverage stay open in the plan.

## Verification

- `uv run pytest src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -q`
  passed.
- `uv run pytest src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -q`
  passed.
- `uv run ruff check src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`
  passed.
- `uv run ty check src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`
  passed.
