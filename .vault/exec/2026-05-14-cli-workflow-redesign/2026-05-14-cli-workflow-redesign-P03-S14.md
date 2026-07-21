---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S14'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Exclude filing schedules, deadline windows, live cross references, filing application links, and portal read or write links from Modelo 145

## Scope

- `registry/aeat/modelos`

## Description

- Keep Modelo 145 free of filing schedules, deadline windows, live cross references, filing application links, and portal surfaces.
- Verify the negative surface contract through the focused registry foundation test.
- Preserve the ADR boundary that Modelo 145 is processed before the payer, not electronically filed with AEAT.

## Outcome

- The Modelo 145 revision has no `filing_schedules`, `deadline_windows`, or `live_cross_references`.
- The registered application-link surfaces do not include `filing`, `deadline`, or `portal`.
- Review found no active filing/live/deadline/portal overclaim in the repaired state.

## Notes

- No CLI or backend surfaces were added in this step.
