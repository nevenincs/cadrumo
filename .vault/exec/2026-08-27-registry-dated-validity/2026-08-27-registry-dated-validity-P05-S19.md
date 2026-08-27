---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:f22da40b77c00d4f6fb28cdd1a46570c5901beda52fba7c9114d869c825b795d'
step_id: 'S19'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Count the tier c) rehabilitation window in calendar years rather than in days, relocating the leap-clamping year shift out of the retention domain into a neutrally named core primitive both consumers read, and retiring the days-declared registry parameter across every revision that carried it so no declaration describes a unit the code no longer uses

## Scope

- `src/cadrumo/core/calendar_shift.py and src/cadrumo/domain/fincas/ and src/cadrumo/domain/retention/ and src/cadrumo/_data/registry/aeat/modelos/100/revisions/`

## Changes

- `A` `src/cadrumo/core/calendar_shift.py`
- `M` `src/cadrumo/domain/retention/_floor.py`
- `M` `src/cadrumo/domain/retention/__init__.py`
- `M` `src/cadrumo/domain/retention/tests/test_floor.py`
- `M` `src/cadrumo/application/overview/_explain.py`
- `M` `src/cadrumo/application/overview/tests/test_explain.py`
- `M` `src/cadrumo/domain/fincas/_tier_resolver.py`
- `M` `src/cadrumo/domain/fincas/tests/test_tier_resolver.py`
- `M` `src/cadrumo/domain/fincas/tests/test_threshold_registry_grounded.py`
- `A` `src/cadrumo/domain/fincas/tests/test_rehab_lookback_is_calendar_relative.py`
- `R` `renta-<year>-rental-rehab-lookback-days.toml -> renta-<year>-rental-rehab-lookback-years.toml` (6 revisions)
- `verify:` `pytest src/cadrumo/domain/fincas src/cadrumo/domain/retention` -> `pass`
- `verify:` `out-of-tree mutation, 2 proofs plus 2 controls` -> `pass`

## Notes

RELOCATION. add_prescription_years was calendar-year arithmetic with a leap clamp
living in domain/retention under a prescription-specific name, reachable only through
that package's facade. A second domain needing the same arithmetic is the point at
which a canonical home has to be nominated, so it moved to
core.calendar_shift.shift_by_calendar_years with every consumer updated in the same
change and the old name deleted rather than aliased. Five files, including the gate
that pins the name to prove the arithmetic is delegated rather than re-inlined.

A TEST ENCODED THE DEFECT AS THE CONTRACT. test_rehab_finished_731_days_before_falls
_through asserted TIER_50 for a rehabilitation finished 2023-06-01 against a contract
celebrated 2025-06-01 -- exactly two calendar years, and 731 days because 2024 is a leap
year. The suite was defending the day count against the article. It was corrected to
assert TIER_60_REHAB and renamed, with a sibling case pinning that the window is still
bounded one day earlier.

THE PARAMETER DECISION, carried through. The days declaration was retired in all six
revisions that carried it and re-declared in years, so no parameter describes a unit
the code no longer reads. A shipped gate reds if any revision re-declares it in days.

HARNESS ERRORS, recorded. Two of the four bite proofs were written with inverted
assertions -- one treated a correctly-denying retired rule as a failure, the other
treated a correctly-widened leap boundary as a narrowing. Both were corrected before
the recorded pass. This is the third tick in this campaign where a proof lied in my
favour, which is the argument for reading every proof's failure text rather than its
verdict.

A registry-validation red seen mid-tick (rd-1065-2007:art-33/34 corpus anchors) was a
peer's uncommitted edit that they reverted themselves; no peer work was lost and the
final run is clean without it.
