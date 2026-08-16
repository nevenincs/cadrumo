---
generated: true
tags:
  - '#index'
  - '#compatibility-lifecycle'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:fd75e250780154cfe922bd016e14e5c7cbe6257e72711b9da256ec995f93d35a'
related:
  - '[[2026-07-09-compatibility-lifecycle-P01-S01]]'
  - '[[2026-07-09-compatibility-lifecycle-P01-S02]]'
  - '[[2026-07-09-compatibility-lifecycle-P01-S03]]'
  - '[[2026-07-09-compatibility-lifecycle-P01-S04]]'
  - '[[2026-07-09-compatibility-lifecycle-P01-S05]]'
  - '[[2026-07-09-compatibility-lifecycle-P02-S06]]'
  - '[[2026-07-09-compatibility-lifecycle-P02-S07]]'
  - '[[2026-07-09-compatibility-lifecycle-P03-S08]]'
  - '[[2026-07-09-compatibility-lifecycle-adr]]'
  - '[[2026-07-09-compatibility-lifecycle-audit]]'
  - '[[2026-07-09-compatibility-lifecycle-plan]]'
  - '[[2026-07-09-compatibility-lifecycle-research]]'
  - '[[2026-07-10-compatibility-lifecycle-reference]]'
---

# `compatibility-lifecycle` feature index

Auto-generated index of all documents tagged with `#compatibility-lifecycle`.

## Documents

### adr

- `2026-07-09-compatibility-lifecycle-adr` - `compatibility-lifecycle` adr: `compatibility-lifecycle checkpoint: regime-switched dormant durability governance` | (**status:** `accepted`)

### audit

- `2026-07-09-compatibility-lifecycle-audit` - `compatibility-lifecycle` audit: `honesty review (campaign close): PASS + verified findings`

### exec

- `2026-07-09-compatibility-lifecycle-P01-S01` - Add the core regime module: CompatibilityRegime enum, one-way COMPATIBILITY_REGIME=PRE_RELEASE constant, RELEASED_FORMAT_FLOORS=None, and pure expected_floor/lineage_obligations predicates
- `2026-07-09-compatibility-lifecycle-P01-S02` - Refactor the three tier lineage gates to assert floor == expected_floor(regime, key, current, floors) via the core facade, behaviour-identical while PRE_RELEASE
- `2026-07-09-compatibility-lifecycle-P01-S03` - Add RELEASED-branch synthetic-input tests proving the future teeth (frozen floor, upgrader/fixture obligations) without flipping the constant or monkeypatching
- `2026-07-09-compatibility-lifecycle-P01-S04` - Add the central repo-wide gate: version-milestone tripwire, one-way coherence, and enrollment over the live constants
- `2026-07-09-compatibility-lifecycle-P01-S05` - Ship the empty cross-version fixture-corpus harness (directory + vacuous coverage assertion)
- `2026-07-09-compatibility-lifecycle-P02-S06` - Author the companion compatibility-lifecycle-checkpoint rule at the vaultspec source and add the no-legacy Status cross-reference
- `2026-07-09-compatibility-lifecycle-P02-S07` - Propagate rule sources to provider copies via vaultspec-core sync
- `2026-07-09-compatibility-lifecycle-P03-S08` - Fresh-context honesty review of the dormant mechanism and governance per aeat-campaign-close-honesty-review

### plan

- `2026-07-09-compatibility-lifecycle-plan` - `compatibility-lifecycle` plan

### reference

- `2026-07-10-compatibility-lifecycle-reference` - `compatibility-lifecycle` reference: `release-checkpoint flip checklist`

### research

- `2026-07-09-compatibility-lifecycle-research` - `compatibility-lifecycle` research: `compatibility-lifecycle checkpoint governance`
