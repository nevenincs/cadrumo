---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:c293503e3c789e3d9a9678674ac76cfb437740f20d81c6662b5a2fd87fc528df'
step_id: 'S12'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Promote the canonical relation consumption predicate

## Scope

- `src/cadrumo/domain/calculations/registry/_handoffs.py`
- `src/cadrumo/domain/calculations/registry/__init__.py`
- `src/cadrumo/domain/calculations/registry/tests/test_cross_period_relation_consumption.py`
- `src/cadrumo/domain/calculations/registry/tests/test_cross_dependency_contract.py`

## Description

- Promote `relation_consumption_index` and `relation_is_consumed` from test-private logic into the registry handoff authority and public facade.
- Cover primary casilla bindings, alternate casilla bindings, formula relation references, and formula binding references through production runtime-graph traversal.
- Re-point both registry consumption gates to the production functions while retaining algorithm-only relation references as an explicit additive test concern.
- Add a real bundled M390 regression whose relation is consumed only through an alternate binding.

## Outcome

- The consumption predicate now has one production owner and the retired test-private walker, index, predicate, and duplicated formula-binding helpers are deleted.
- Both owning test modules pass 18 tests; Ruff, format, BasedPyright, collection, facade-identity, prohibited-construct, structural, and diff gates are green.
- Formal review reported PASS with no findings.

## Notes

- The fourth channel exposed three existing factual-evidence relations declared as alternate bindings. The obsolete claim that all factual evidence is unconsumed was deleted; the surviving invariant is precise: only factual evidence may remain unconsumed, while alternate evidence channels remain honestly visible as consumed.
