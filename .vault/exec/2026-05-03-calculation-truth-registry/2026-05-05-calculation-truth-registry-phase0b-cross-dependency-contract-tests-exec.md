---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `Phase 0B` `cross-dependency-contract-tests`

Added generalized cross-model dependency contract tests.

- Modified: `src/aeat/domain/calculations/registry/_runtime_graph.py`
- Created: `src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The registry test suite now checks cross-model dependency rules as stable tax
system invariants. The tests verify dependency-role semantics,
source-requirement derivation for target periods, consumption of calculation
relations by formula or algorithm paths, and attachment of formula relation
dependencies to computed casillas.

The scaffold is generalized across loaded modelos and does not copy modelo
schema definitions into tests.

## Tests

Focused validation was run with:

- `uv run pytest src/aeat/domain/calculations/registry/test_cross_dependency_contract.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/_runtime_graph.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
- `uv run ty check src/aeat/domain/calculations/registry/_runtime_graph.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
