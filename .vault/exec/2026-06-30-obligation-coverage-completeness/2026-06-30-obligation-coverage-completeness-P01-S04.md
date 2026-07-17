---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Project the coverage advisory as a default-visible Notice on calendar, agenda, and backlog.

## Scope

- `src/aeat/entrypoints/cli/_overview.py`

## Description

- Add `overview_coverage_notices`, projecting the report's `advised` bucket into a
  single typed `Notice` (warning when a known-applicable obligation has no window;
  info otherwise), carrying the modelo-to-reason map on the notice context and a
  runnable `overview explain` suggestion.
- Wire the notice into the calendar, agenda, and backlog CLI commands and add a
  parallel text line.
- Exclude `coverage` from the payload dumps so the advisory rides the canonical
  `Notice` channel per the notices rule, not a bespoke result field.

## Outcome

The default surface now emits the advisory without the operator needing
`--show-suppressed`. Agenda and backlog CLI verb tests (10) and rendering unit
tests (11) pass. The locale key is served from its English `tr(..., default=...)`
fallback pending the peer duplicate-key clearance recorded in P02.

## Notes
