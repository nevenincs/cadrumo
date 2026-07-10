---
tags:
  - '#exec'
  - '#compatibility-lifecycle'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S02'
related:
  - "[[2026-07-09-compatibility-lifecycle-plan]]"
---

# Refactor the three tier lineage gates to assert floor == expected_floor(regime, key, current, floors) via the core facade, behaviour-identical while PRE_RELEASE

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_schema_lineage.py`

## Description

## Outcome

Landed in commit ffb2f94605 - dormant compatibility-lifecycle mechanism: core regime module (enum + one-way COMPATIBILITY_REGIME=PRE_RELEASE + RELEASED_FORMAT_FLOORS=None + pure expected_floor/lineage_obligations predicates), regime-aware tier gates (behaviour-identical today), synthetic RELEASED-branch tests, central tripwire/coherence/enrollment gate, empty fixture harness. 34 passed, dormant confirmed.

## Notes
