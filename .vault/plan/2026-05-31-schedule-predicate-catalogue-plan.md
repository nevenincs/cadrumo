---
tags:
  - '#plan'
  - '#schedule-predicate-catalogue'
date: '2026-05-31'
modified: '2026-05-31'
tier: L2
related:
  - '[[2026-05-31-schedule-predicate-catalogue-adr]]'
  - '[[2026-05-31-schedule-predicate-catalogue-research]]'
---

# schedule-predicate-catalogue plan

## Intent

Close task #560: schedule-predicate field catalogue compile-time validation.
The compile-time gate is substantially present in _registry_contract.py but three
gaps remain. This plan closes all three gaps in two phases.

## Steps

### Phase `P01` - eager load gate and alias documentation

- [x] `P01.S01` - add validate_registry call in load authority; `src/aeat/domain/calculations/registry/_authority.py`.
- [x] `P01.S02` - document alias shims in resolve profile fact; `src/aeat/domain/calculations/registry/_registry_contract.py`.

#### Detail: S01 -- add validate_registry() call in _load_authority

### S01 -- add validate_registry() call in _load_authority

Add a  call inside 
in , immediately after
 returns and before the  dataclass
is constructed. This makes the predicate-field check fire at registry load, not at
the first  call.

Verification gate: run 
and confirm it passes. Run 
to confirm the CI gate still passes.

#### Detail: S02 -- document alias shims in _resolve_profile_fact

Add inline comments to the two hardcoded attribute aliases in 
in  (lines 81-85) explaining
which schema predicate path each alias serves and why the alias exists.
No behavioural change.

Verification gate: 
passes unchanged.

### Phase `P02` - proof tests for the two uncovered predicate surfaces

- [x] `P02.S03` - add proof test for filing schedule predicate surface; `src/aeat/domain/calculations/registry/test_filing_schedule_selection.py`.
- [x] `P02.S04` - add proof test for deadline window predicate surface; `src/aeat/domain/calculations/registry/test_filing_schedule_selection.py`.

#### Detail: S03 -- proof test for filing_schedule surface

Add a test function in
 that:
- Loads the committed registry tree.
- Takes a committed modelo revision that has filing_schedules with profile_conditions
  (e.g. modelo 111 revision 2019-y-siguientes).
- Injects a synthetic ProfilePredicateDefinition with field=unknown_predicate_field
  as one of the profile_conditions.
- Calls validate_user_profile_registry_contract([mutated_modelo], schema).
- Asserts that the returned report contains an issue with surface=filing_schedule,
  severity=ERROR, and selector=unknown_predicate_field.

Verification gate: the new test passes.

#### Detail: S04 -- proof test for deadline_window surface

Add a test function in the same file or in
 that:
- Takes a committed modelo revision that has deadline_windows with applicability_conditions
  (e.g. modelo 115 or 130 revision).
- Injects a synthetic ProfilePredicateDefinition with field=unknown_predicate_field
  as one of the applicability_conditions.
- Calls validate_user_profile_registry_contract([mutated_modelo], schema).
- Asserts surface=deadline_window, severity=ERROR, selector=unknown_predicate_field.

Verification gate: the new test passes.

## Acceptance criteria

- All four steps committed, one commit per step.
- The five existing tests in test_authority.py, test_registry_contract.py, and
  test_schedules.py continue to pass.
- The two new proof tests pass.
- No broken predicates surface during the eager validate_registry() call on the
  committed registry (all 22 predicate paths are already valid).

## Closure note -- 2026-06-01

Plan complete. All four Steps have committed `Step Record` artefacts under
`.vault/exec/2026-05-31-schedule-predicate-catalogue/` (P01-S01, P01-S02,
P02-S03, P02-S04). The proof-test sweep landed
`unknown_predicate_field` surface coverage in
`src/aeat/domain/calculations/registry/test_filing_schedule_selection.py`
per the verification gates of P02-S03 and P02-S04. Plan body now retains
the historical detail notes plus the canonical row ledger added during
the Phase Two cleanup pass; closure is asserted via the four exec records
and matching completed step rows.
