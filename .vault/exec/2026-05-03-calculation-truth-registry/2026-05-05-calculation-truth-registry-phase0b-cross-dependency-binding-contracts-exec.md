---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `Phase 0B` `cross-dependency-binding-contracts`

Extended cross-model dependency contract tests at binding and legal-basis level.

- Modified: `src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The registry contract suite now verifies that each relation target binding
mirrors the relation source modelo, output/casilla selector, source periods, and
aggregation operation. Formula dependencies that consume relations must also
carry the legal basis declared by the relation.

These checks exercise committed registry behaviour and do not introduce schema
fixtures or transition-state assertions.

## Tests

Focused validation was run with:

- `uv run pytest src/aeat/domain/calculations/registry/test_cross_dependency_contract.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
