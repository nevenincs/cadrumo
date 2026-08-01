---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:213612bd1863ea5b4bc572e514e30e58cafbbe8012eb81c496ae84f70a1282ff'
step_id: 'S07'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Populate the CalculationRevision roundtrip fixture with a non-default period_code entry in input_values_by_casilla_id

## Scope

- `src/cadrumo/adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py`

## Description

- Locate the calculation-revision encrypted-boundary roundtrip fixture, which is not where this Step's scope line says it is.
- Add a non-default period-code entry to the fixture's string replay mapping.
- Assert the entry survives the encrypted save-and-load cycle verbatim.

## Outcome

The intent is satisfied. The fully-populated roundtrip fixture now carries a period-code entry alongside its decimal-shaped entry, and the roundtrip test asserts the token survives the encrypted boundary unchanged in addition to the existing whole-object equality.

The entry earns its place rather than padding the fixture. Every other value in that mapping is decimal-shaped, so a boundary regression coercing the mapping's values through a numeric parser would have round-tripped cleanly and gone unseen. A period code is the only value in the fixture that such a regression cannot survive.

The Step's scope line named the domain modelos test package at dispatch, where no calculation-revision encrypted-boundary roundtrip fixture exists. The real fixture is the persistence-adapter profile package, in the calculation-repository roundtrip module. That correction was reported rather than silently worked around, and the amending ruling has since rewritten the Step's scope line to the correct path, so the row and the landed diff now agree.

## Notes

Checked on satisfied intent against the amended scope line. Anyone auditing an older copy of the plan should expect the diff in the persistence-adapter package, not the domain package the original row named.

A fixture constant naming the token tripped a hardcoded-credential lint rule on its suffix and was renamed. Behaviour is unchanged; the rename keeps the lint gate honest rather than suppressed.
