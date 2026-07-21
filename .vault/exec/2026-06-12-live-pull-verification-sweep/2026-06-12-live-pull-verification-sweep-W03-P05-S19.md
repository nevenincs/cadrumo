---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S19'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
---

# Exercise censo CLI commands for pull, show, compare, apply, and calendar projection, proving authenticated Modelo 036 facts drive obligations and typed `core.Period` identities connect those obligations to filed/justificante evidence

## Scope

- `src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py src/aeat/entrypoints/cli/_overview.py`

## Description

- Re-grounded the censo CLI row with `vaultspec-rag` against the accepted
  operator-manual enrolment decision and the current CLI/application surface.
- Confirmed that the entire `config profile censo pull`, `show`, `compare`, and
  `apply` family was retired with its snapshot operand and G313 scrape chain.
- Reconciled this row against the replacement workflow: `config profile edit`
  records operator-declared censal facts while the calendar retains its
  unverified-enrolment posture.

## Outcome

Superseded, not delivered. Exercising the retired censo CLI family against
authenticated Modelo 036 data is no longer a valid acceptance target. Keeping
this row open would direct an operator toward a command family and AEAT read
approach that the accepted safety decision explicitly removed.

The remaining `src/aeat/application/user_profile/_censo_sync.py` surface has no
CLI capture/compare/apply operation and emits no AEAT-verified censo provenance.
Consequently, calendar projection continues to distinguish operator-declared
facts from verified censo enrolment rather than claiming a local-only success as
remote evidence.

## Notes

No legacy censo CLI command was run and no authenticated census result is
claimed. A future automatic censo CLI may be considered only after a new ADR
for a genuine AEAT consulta-only endpoint.
