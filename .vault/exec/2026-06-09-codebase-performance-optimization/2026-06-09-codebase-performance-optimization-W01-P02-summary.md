---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - '[[2026-06-09-codebase-performance-optimization-plan]]'
---

# `codebase-performance-optimization` `W01.P02` summary

Completed Phase 2 of Wave 1, introducing manual caching for formula AST and casilla reference lookup traversal to speed up graph execution and solve unhashable Pydantic type errors.

- Modified: `src/aeat/domain/calculations/registry/_runtime_graph.py`
- Created: `.vault/exec/2026-06-09-codebase-performance-optimization/2026-06-09-codebase-performance-optimization-W01-P02-S04.md`
- Created: `.vault/exec/2026-06-09-codebase-performance-optimization/2026-06-09-codebase-performance-optimization-W01-P02-S05.md`

## Description

Formula evaluation requires sorting computed casillas and resolving reference paths. Previously, `lru_cache` was used for `_casilla_reference_resolver`, `input_casilla_alias_map`, and `formula_evaluation_order`, which caused `TypeError: unhashable type: 'dict'` because the `ModeloRevision` objects contain unhashable Pydantic structures.
We replaced `@lru_cache` decorators with manual dictionary caches (`_RESOLVER_CACHE`, `_ALIAS_MAP_CACHE`, `_EVALUATION_ORDER_CACHE`) keyed on `id(revision)`. Additionally, the AST formula expression collectors are cached, which avoids repetitive deep nested parsing of formula ASTs during calculations.

## Tests

- Pytest ran successfully on `src/aeat/domain/calculations/registry/tests/test_authority.py` with all 7 tests passing in 1.00s.
