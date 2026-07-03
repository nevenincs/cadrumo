---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S05'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Add the coverage-completeness invariant test.

## Scope

- `src/aeat/application/overview/tests/test_obligation_coverage.py`

## Description

- Add the coverage-completeness invariant test asserting the report partitions the
  full `registry_modelo_codes()` set with pairwise-disjoint buckets, for the
  paying-autonomo, landlord, and sociedad personas.
- Pin the Modelo-190 regression: it must appear in `advised` with the
  window-missing reason, never silently absent.
- Assert the out-of-scope bucket equals the central declaration, and that the
  calendar, agenda, and backlog all attach the coverage report by default.

## Outcome

The invariant is the anti-silent-drop gate that would have caught Modelo 190. All 7
tests pass. This is a structural test (no external numeric oracle), consistent with
the no-tautological-calculation-tests rule.

## Notes

The 8 red tests in `test_overview_calendar_verb.py` (multi-profile / local-evidence
`StorageValidationError` and profile-label redaction) and two repo-wide literal
gates were confirmed pre-existing on this branch, owned by peer WIP outside this
feature surface (uuid-identity + in-flight CLI checkpoints), per the
full-tree-gate-must-distinguish-owner rule.

## Notes
