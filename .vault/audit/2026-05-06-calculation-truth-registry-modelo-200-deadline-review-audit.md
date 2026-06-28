---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-06-calculation-truth-registry-modelo-200-deadline-exec]]'
---



# `calculation-truth-registry` Code Review

REVIEW-001 | INFO | No findings

The Modelo 200 deadline slice keeps legal and source authority in the central
registry. Python changes are limited to behaviour tests that load the committed
registry, build a snapshot, validate catalogue references, and verify that the
cited BOE corpus supports the deadline and domiciliation dates.

The implementation does not introduce compatibility shims, generated rule
paths, hardcoded Python legal constants, migration tests, or transient
development-state assertions.

## Verification

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_200_registry.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -q`
  passed.
- `uv run ruff check src/aeat/domain/calculations/registry/test_modelo_200_registry.py`
  passed.
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_200_registry.py`
  passed.
- Focused Modelo 200 `RegistryValidator` pass completed.
