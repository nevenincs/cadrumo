---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S445'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Remove retired annual filing-year-plus-one fallbacks from plazo and overview calendar consumers, require exact tax-year deadline windows, and prove unregistered M180 2023 and M100 2019 annual work fails closed without borrowing a future campaign.

## Scope

- `src/aeat/{domain/deadlines/_plazo.py`
- `application/overview/_calendar.py} src/aeat/**/tests/`

## Description

- Used RAG and direct source tracing to confirm two stale annual `filing_year + 1` selection policies outside DeadlineEngine.
- Removed the fallback from plazo resolution and local-work-unit overview calendar projection, requiring exact modelo, tax-year, and registry-token matching.
- Added parameterized real-registry regressions for missing M180 2023/0A and M100 2019/0A windows.
- Exercised overview with real WorkUnit records and the public calendar to prove absent windows do not project into M180 2024 or M100 2020 campaigns.
- Ran the focused deadline/overview suite, owned Ruff, and a path-scoped whitespace check.

## Outcome

- Annual deadline selection now has one tax-year contract across registry, DeadlineEngine, plazo resolution, workflow, and overview consumers.
- Missing exact annual windows return no deadline; no consumer borrows a future campaign.
- Focused deadline and overview coverage passed 74 tests in 22.28 seconds; owned Ruff and whitespace checks passed.

## Notes

- Existing concurrent `period.year` to `period.filing_year` changes in calendar code were preserved and are not claimed by this step.
