---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `Phase 0B` `source-output-contracts`

Extended cross-model dependency tests to cover source-modelo output contracts.

- Modified: `src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The dependency contract suite now checks that each relation source output
resolves in every selected source revision to either a filing-grade source
casilla or a declared algorithm output. Informational casillas cannot satisfy a
calculation relation source output.

## Tests

Focused validation was run with:

- `uv run pytest src/aeat/domain/calculations/registry/test_cross_dependency_contract.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_cross_dependency_contract.py`
