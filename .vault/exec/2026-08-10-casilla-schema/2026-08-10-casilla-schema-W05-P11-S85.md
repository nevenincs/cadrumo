---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:a03c5c16ded4c310a6a72b8679de9c5a4ee6488bad62d5ee288f9b03d30a8335'
step_id: 'S85'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

# replace the relation-handoff applicability hard counts with count-free semantic invariants and a bite proof, making the complete owning module green

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_relation_handoff_inventory.py`

## Description

- Delete the seven hardcoded tallies (row, active, not-applicable, and the three clean-state mode sums) that pinned a moment of the registry corpus.
- Derive the expected relation-period row set from the authority itself - every relation-bearing revision's declared periods crossed with its declared relations - and assert set equality plus a derived row count.
- Assert the applicability partition is total against the row count and that no row is unresolved.
- Assert non-vacuity by requiring the corpus to populate both applicability states and all three clean-state modes as sets, never as counts.
- Join each row back to its revision's own `DependencyClassificationDefinition` and assert the carried classification fields and the derived clean-state contract agree with the registry declaration.
- Assert applicability through its observable source contract: an active row resolved a requirement, an excluded row is excluded by the relation's own declared target periods and carries no source contract.

## Outcome

The complete owning module is green: 3 passed in 27.32 seconds. `ruff format --check` and `ruff check` both pass on the target.

The replacement invariants were proven to bite twice, each by a runtime patch loaded from outside the repository as a pytest plugin, so no tracked file was mutated for the proof:

- Forcing the clean-state projection to answer `required` for every classification reds the mode-presence assertion (`assert {'required'} == {'advisory', 'conditional', 'required'}`).
- Dropping one projected row per period reds the registry-derived row-set equality at the totality assertion.

Both runs restored to green immediately, since neither touched the working tree.

## Notes

The retired tallies encoded 108 rows, 81 active, 27 not applicable, and 73/22/13 clean-state modes. Every one of those numbers is now recomputed from the loaded authority at test time, so a registry revision, period, or relation added or withdrawn moves both sides of each assertion together rather than requiring a constant to be edited. No data loss and no destructive Git operation occurred.
