---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S01'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Generate the coverage report: derive the candidate query surface from calc-grade casilla labels/sections and legal-catalogue provision vocabulary, list every derivable target with no inbound relevance entry, and commit the report

## Scope

- `dev/docs/terminology/`
- `.vault/audit/`

## Description

- Dispatch the coverage-generator build to an opus executor; verify and land.
- Implement `dev/docs/terminology/_coverage.py`: typed coverage over the four
  derivable target surfaces (approved concepts, casilla records, CLI records,
  legal provisions) joined against the committed relevance mapping on the
  canonical `to_search_record(...).id` funnel; legal mirrors the resolver's
  `legal:{provision_id}` shape.
- Add the `python -m dev.docs.terminology.coverage report` CLI and six
  real-behaviour gates; run the generator and commit the baseline report.

## Outcome

Baseline committed at
`src/cadrumo/_data/terminology/evaluation/coverage-report.json` (commit
`3bd971a3a2`): concepts 29/29 covered, casillas 13/6330, CLI 0/1468, legal
11/555, 120 orphan mapping targets on the code/page grounding surfaces, 173
referenced targets. Report deterministic; 6/6 tests green; ruff clean.

## Notes

W03 reading: prioritise legal provisions and calc-grade casilla families
over chasing all 6330 casillas; the CLI surface is navigational and may
warrant a lower coverage target.
