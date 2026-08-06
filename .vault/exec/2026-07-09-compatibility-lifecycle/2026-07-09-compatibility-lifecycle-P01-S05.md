---
tags:
  - '#exec'
  - '#compatibility-lifecycle'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:819d04d39054f01babbb9ab673b44034426b6744af9a61610185ad8f893cca53'
step_id: 'S05'
related:
  - "[[2026-07-09-compatibility-lifecycle-plan]]"
---

# Ship the empty cross-version fixture-corpus harness (directory + vacuous coverage assertion)

## Scope

- `fabricate no old-version fixture`
- `src/aeat/_data/compat_fixtures`

## Description

## Outcome

Landed in commit ffb2f94605 - dormant compatibility-lifecycle mechanism: core regime module (enum + one-way COMPATIBILITY_REGIME=PRE_RELEASE + RELEASED_FORMAT_FLOORS=None + pure expected_floor/lineage_obligations predicates), regime-aware tier gates (behaviour-identical today), synthetic RELEASED-branch tests, central tripwire/coherence/enrollment gate, empty fixture harness. 34 passed, dormant confirmed.

## Notes
