---
tags:
  - '#plan'
  - '#compatibility-lifecycle'
date: '2026-07-09'
modified: '2026-07-10'
tier: L2
related:
  - '[[2026-07-09-compatibility-lifecycle-adr]]'
  - '[[2026-07-09-compatibility-lifecycle-research]]'
---

# `compatibility-lifecycle` plan

### Phase `P01` - Dormant enforcement mechanism

Install the regime constant, pure predicates, regime-aware tier gates (behaviour-identical today), synthetic RELEASED-branch tests, central tripwire/coherence/enrollment gate, and the empty fixture harness — all a no-op while PRE_RELEASE.

- [x] `P01.S01` - Add the core regime module: CompatibilityRegime enum, one-way COMPATIBILITY_REGIME=PRE_RELEASE constant, RELEASED_FORMAT_FLOORS=None, and pure expected_floor/lineage_obligations predicates; `re-export via the aeat.core facade; `src/aeat/core/compatibility_lifecycle.py`.
- [x] `P01.S02` - Refactor the three tier lineage gates to assert floor == expected_floor(regime, key, current, floors) via the core facade, behaviour-identical while PRE_RELEASE; `src/aeat/adapters/persistence/storage/tests/test_schema_lineage.py`.
- [x] `P01.S03` - Add RELEASED-branch synthetic-input tests proving the future teeth (frozen floor, upgrader/fixture obligations) without flipping the constant or monkeypatching; `src/aeat/core/tests/test_compatibility_lifecycle.py`.
- [x] `P01.S04` - Add the central repo-wide gate: version-milestone tripwire, one-way coherence, and enrollment over the live constants; `src/aeat/tests/test_compatibility_lifecycle_gate.py`.
- [x] `P01.S05` - Ship the empty cross-version fixture-corpus harness (directory + vacuous coverage assertion); `fabricate no old-version fixture; `src/aeat/_data/compat_fixtures`.

### Phase `P02` - Governance rule

Author the companion compatibility-lifecycle-checkpoint rule at the vaultspec source, add the no-legacy Status cross-reference, and sync to provider copies; no-legacy stays verbatim.

- [x] `P02.S06` - Author the companion compatibility-lifecycle-checkpoint rule at the vaultspec source and add the no-legacy Status cross-reference; `.vaultspec/rules/compatibility-lifecycle-checkpoint.md`.
- [x] `P02.S07` - Propagate rule sources to provider copies via vaultspec-core sync; `.claude/rules`.

### Phase `P03` - Campaign close

Honesty review of the dormant mechanism + governance, then exec records and feature index.

- [x] `P03.S08` - Fresh-context honesty review of the dormant mechanism and governance per aeat-campaign-close-honesty-review; `.vault/audit`.

## Description

## Steps

## Parallelization

## Verification
