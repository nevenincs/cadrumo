---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S30'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W04.P08.S30 Resume Exact Id Validation

Scope: reuse shared CLI exact-id validation for the legacy resume escape hatch.

## Description

- Replace ad hoc resume-target shape handling in the CLI command with shared `validate_work_unit_id` and `validate_calculation_revision_id` helpers.
- Keep workflow-run-id shape validation inside the workflow application resume resolver.
- Parse `--select` through the shared revision selector parser before application resolution.
- Remove local resume regex branching from the CLI module.

## Outcome

The CLI no longer owns work-unit or calculation-revision id validation logic for resume. Exact-id validation and selector parsing are centralized through existing support helpers and the application facade.

## Notes

Legacy positional workflow-run and work-unit ids remain supported, but the preferred operator-facing path is the natural modelo/year/period target.
