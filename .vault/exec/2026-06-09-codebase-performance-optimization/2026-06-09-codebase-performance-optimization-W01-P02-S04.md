---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S04'
related:
  - "[[2026-06-09-codebase-performance-optimization-plan]]"
---




# Add lru_cache to _casilla_reference_resolver, input_casilla_alias_map, and formula_evaluation_order

## Scope

- `src/aeat/domain/calculations/registry/_runtime_graph.py`

## Description

- Replaced `@lru_cache` on `_casilla_reference_resolver`, `input_casilla_alias_map`, and `formula_evaluation_order` with manual dictionary caches (`_RESOLVER_CACHE`, `_ALIAS_MAP_CACHE`, `_EVALUATION_ORDER_CACHE`) keyed on `id(revision)` to avoid Pydantic models' `unhashable type: 'dict'` failures.

## Outcome

- Done. The unhashable type error was successfully eliminated and evaluation order caching works perfectly.

## Notes

