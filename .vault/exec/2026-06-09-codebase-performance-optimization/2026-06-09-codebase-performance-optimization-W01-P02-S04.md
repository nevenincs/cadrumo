---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-07-17'
body_hash: 'sha256:8a586e03c6e0a7585a47e5b326597840f4ea7aec55038a083548fdfca0a49439'
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
