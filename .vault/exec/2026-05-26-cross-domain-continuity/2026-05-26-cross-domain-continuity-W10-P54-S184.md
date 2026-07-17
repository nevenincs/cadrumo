---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S184'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# modelo-349-2025-2026-deadline-verification

## Scope

- `src/aeat/_data/registry/aeat/modelos/349/`

## Description

- Grounded the monthly and quarterly schedules against the current AEAT Modelo 349 guidance and Orden EHA/769/2010 article 10.
- Resolved the live registry for 2025 and 2026, confirming all sixteen monthly and quarterly tokens for each year and the July, December, and fourth-quarter statutory exceptions.
- Extended the committed-registry test with 2026 exact-date cases for normal monthly and quarterly windows plus each exceptional closure shape.
- Ran the Modelo 349 registry and deadline-engine suites: 58 passed; `ruff check` passed.
- Obtained an independent review of legal grounding, cadence predicates, deadline-engine selection, and the test diff.

## Outcome

Modelo 349 has complete 2025 and 2026 monthly and quarterly deadline coverage, including the legally required July, December, and fourth-quarter exceptions.

## Notes

The threshold fact is a caller-owned profile fact used to choose monthly versus quarterly cadence; deriving its historical rolling threshold is outside this deadline-window step.
