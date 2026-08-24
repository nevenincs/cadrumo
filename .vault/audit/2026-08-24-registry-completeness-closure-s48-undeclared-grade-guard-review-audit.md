---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:f742c2b7e56d1299eb54ce35006d27734aa25cd3209c1e55e6d65944b8ec8c54'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` audit: `S48 undeclared-grade guard review`

## Scope

Reviewed commit `d931cccb0f3e3b2bebcc1eec5a02b94f268d598b`, specifically the added
contradictory construction and revalidated mutation cases for
`TemporalRevisionCoverage`.

## Findings

### all-non-null-grades-not-proven | medium | The test proves one declared grade, not the complete non-null contract

`TemporalRevisionCoverage._validate_outcome_shape` rejects every non-null
`declared_authority_grade` for an `undeclared_authority_grade` refusal. The two S48
cases use only `RegistryAuthorityGrade.APPLICABILITY`. The real authority-grade
enum also includes `CALCULATION` and `FILING`, so a plausible weakened guard that
refuses only applicability would keep both new tests green while allowing a
contradictory calculation- or filing-grade refusal. The committed guardless-copy
experiment proves removal of the condition, but it does not prove the required
all-non-null semantic property.

## Recommendations

Open one follow-up Step that parameterizes both construction paths across every
`RegistryAuthorityGrade` member and mutates the isolated guard to reject only
applicability. The focused suite must fail for calculation and filing contradictions
under that weakened guard while passing against the current implementation.
