---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:f751639a8f0fc5d5480f158f52281a2288fc7ef0a5e2614eff57e833a22a9686'
step_id: 'S21'
related:
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-14-registry-campaign-sequencing-audit]]'
  - '[[2026-08-14-registry-temporal-coverage-load-closure-census-audit]]'
---

# Close the classification of the six validator modules the load traces showed executing in neither regime, recording for each the entry point that does reach it, because the census disproved the premise that they cannot execute: four are reached from the snapshot reference check on the inspection path, one is reached from the cross-revision validator on every cold load, and one publishes caches and defines no callable so it can never appear in an execution set however live it is, leaving the deletion clause of this row empty unless a member is newly shown dead

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`
- `.vault/audit/`

## Description

This record documents work found already present and ALREADY COMMITTED, at sha
`c72a9e4297134afbecee4a57c06f5acf316e0b67` ("feat(registry): census the load
closure and classify every reachable module (W01.P09.S26)"). It is written
retrospectively from that committed audit and classification module, not from
having performed the classification myself. The commit was authored under the
sibling row `W01.P09.S26`, not under this row's own id — this record exists
because that census, as a side effect of answering S26's question, also fully
answers what this row (`W01.P04.S21`) asks for.

The committed load-closure-census audit (linked in `related:`, finding "none of
the six validators the campaign carried as never executing is unable to
execute, and four of them execute on a traced entry point") and the
committed `dev/registry/load_census_classification.py` name all six validators
this row names, each with the exact entry point the row itself already states:

- `_validate_cross_domain_snapshot`, `_validate_reference_checker`,
  `_validate_reference_sections`, `_validate_references` — classified
  `conditionally_reachable`, trigger "registry snapshot construction:
  build_snapshot and ValidatedRegistryAuthority.snapshot", reached from the
  snapshot-scoped reference check at `_snapshot.py:328`, observed by tracing
  `build_snapshot` across the bundled corpus (53 of 73 modelos reached).
- `_validate_cross_revision_advisory` — classified `conditionally_reachable`,
  trigger "cross-revision contiguity advisory raised during registry
  validation", reached from `_validate_cross_revision`, which runs on every
  cold load; its advisory builders fire only for a corpus with a contiguity
  divergence, which the bundled corpus does not currently present.
- `_validate_cache` — classified `conditionally_reachable`, trigger
  "declaration-only surfaces consumed at import by the load path and by facade
  consumers": it defines no callable the load window could record (it
  publishes the three cache objects `_validate.py:38` binds at import), so its
  absence from every execution set is a property of the trace instrument, not
  of the module.

## Outcome

The row's own deletion clause — "leaving the deletion clause of this row empty
unless a member is newly shown dead" — has no members: the committed census
found none of the six dead, so no code was deleted for this row, and none
should be. The committed audit's own Recommendations section states this
explicitly: "Re-scope `W01.P04.S21` before it executes... The row should record
the reachable caller for each, note that its deletion clause has no members,
and close on the classification rather than on a deletion. This census
supplies the callers." This record is that re-scoped closure: the classification
the row asks for already exists, committed, naming every one of the six
modules and its entry point exactly as the row's own text anticipates.

Verification for this record: independently re-derived the classification via
`load_ledger()` / `reconcile()` in `dev/registry/load_census_classification.py`
and confirmed all six modules present with the stated classifications and
triggers (grep-confirmed at lines 229-232 for the four inspection-path
validators, line 403 for `_validate_cache`, line 429 for
`_validate_cross_revision_advisory`). Re-ran
`pytest src/cadrumo/domain/calculations/registry/tests/test_load_census_classification.py -n 0 -q`
→ `7 passed` in 103.53s, confirming the gate this classification backs is
currently green (zero unclassified members across the 523-module census
universe).

## Notes

This record documents work found already present and committed by a prior
session under a sibling row's commit; it does not represent classification
work performed by the agent writing this record.

**What this record does NOT claim.** The committed audit and census answer
this row's substance completely, but no commit or exec record exists carrying
this row's OWN id (`S21`) as its subject — the classification landed as a
byproduct of `S26`'s broader census, not as `S21`'s own deliverable. Whether
that satisfies "closed" for `S21` specifically, versus needing its own
pointer/cross-reference commit, is a disposition call left to the plan owner;
this record states the evidence rather than pre-judging that call.

This row's deletion-inventory consumption is explicitly none, and the
committed audit itself makes that a positive finding rather than an omission:
the campaign brief's premise (a validator that cannot execute on any machine)
is false for all six named modules.
