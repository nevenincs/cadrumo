---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S03'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Record the current campaign tracker as the canonical wave schedule

## Scope

- `.vault/plan`

## Description

- Create the L3 plan scaffold for the continuation campaign with
  `vaultspec-core vault add plan`.
- Populate five waves, eleven phases, and thirty-two Steps through
  `vaultspec-core vault plan` verbs.
- Add Description, Parallelization, and Verification prose without editing
  canonical identifiers by hand.
- Validate the plan with `vaultspec-core vault plan check`.

## Outcome

The continuation tracker is
`2026-06-30-cli-persona-testimonials-plan.md`. It schedules intake, P0
calculation and data-safety hardening, persona replay, live/legal hardening, and
owner-aware certification as an open-ended campaign queue.

## Notes

The plan currently starts with all execution Steps open except the intake rows
that have matching exec records and are closed by the orchestrator.
