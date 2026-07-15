---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S05'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

# Resolve the period-combined-string findings in docs at root cause per the gate grammar

## Scope

- `docs period tokens`

## Description

- Confirmed no peer WIP under `docs/_sequences` or
  `src/cadrumo/core/tests` before editing.
- Ran `pytest src/cadrumo/core -q -k period_combined_string` at HEAD
  and read the failure output: 10 unallowlisted "year-qualified
  quarterly token" hits across 7 `docs/_sequences/how-to/*.json`
  files (`modelo-130` manual-casilla + quarterly,
  `modelo-303-first-quarter`, `modelo-349-first-quarter`,
  `modelo-390-annual-2025` (4 hits), `quickstart-modelo-130`,
  `verification-reports-modelo-303`).
- Inspected the surrounding lines of every hit: each is the
  `WorkUnit.name` display-name field (`"name": "<modelo>-<year>-<period>"`)
  captured inside a CLI sequence fixture, sitting alongside sibling
  `modelo`/`filing_year` keys — byte-identical in shape to the
  already-allowlisted `modelo-130-first-quarter.json` precedent
  established in a prior campaign. None of the 10 hits are a period
  input/parsing grammar site.
- Extended the existing narrow, path-scoped allowlist rule (rather
  than adding 7 new near-duplicate rules or widening the pattern
  match) to cover all 7 files under one alternation, preserving the
  `pattern_names={"year-qualified quarterly token"}` restriction so
  the rule stays narrow to the one legitimate pattern.
- Re-ran the gate: green. Ran ruff check + format (format applied one
  line-wrap reflow to the extended alternation); re-ran the gate again
  post-format to confirm it still passes.

## Outcome

Landed in commit `42fd4ff979`. `test_repo_has_no_unallowlisted_combined_period_strings`
passes at HEAD. Root-caused: no new fixtures were touched, no pattern
was loosened, and no unrelated finding was muted — the 10 findings
were the same display-label pattern the gate's grammar already
excepts, on 6 newly-captured docs sequence fixtures the allowlist had
not yet enumerated.

## Notes

No incidents. Same exec-record ADR-scaffolding blocker as S04, noted
there; resolved by the time this record was authored.
