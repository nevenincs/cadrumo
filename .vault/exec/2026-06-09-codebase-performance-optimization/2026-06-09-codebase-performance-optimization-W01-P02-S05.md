---
tags:
  - '#exec'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S05'
related:
  - "[[2026-06-09-codebase-performance-optimization-plan]]"
---




# Add lru_cache to expression ref collectors for FormulaExpression

## Scope

- `src/aeat/domain/calculations/registry/_runtime_graph.py`

## Description

- Verify/implement manual dictionary-based caching for expression reference collectors (`expression_casilla_refs`, `expression_relation_refs`, etc.) keyed on `id(expression)`.

## Outcome

- Done. The AST reference collectors are cached, drastically reducing graph traversal overhead for complex formulas.

## Notes

