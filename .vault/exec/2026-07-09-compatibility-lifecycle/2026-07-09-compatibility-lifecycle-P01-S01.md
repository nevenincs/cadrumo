---
tags:
  - '#exec'
  - '#compatibility-lifecycle'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S01'
related:
  - "[[2026-07-09-compatibility-lifecycle-plan]]"
---

# Add the core regime module: CompatibilityRegime enum, one-way COMPATIBILITY_REGIME=PRE_RELEASE constant, RELEASED_FORMAT_FLOORS=None, and pure expected_floor/lineage_obligations predicates

## Scope

- `re-export via the aeat.core facade`
- `src/aeat/core/compatibility_lifecycle.py`

## Description

## Outcome

Landed in commit ffb2f94605 - dormant compatibility-lifecycle mechanism: core regime module (enum + one-way COMPATIBILITY_REGIME=PRE_RELEASE + RELEASED_FORMAT_FLOORS=None + pure expected_floor/lineage_obligations predicates), regime-aware tier gates (behaviour-identical today), synthetic RELEASED-branch tests, central tripwire/coherence/enrollment gate, empty fixture harness. 34 passed, dormant confirmed.

## Notes
