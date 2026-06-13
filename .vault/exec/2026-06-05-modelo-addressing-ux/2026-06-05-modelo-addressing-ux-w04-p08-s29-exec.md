---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S29'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W04.P08.S29 Work Resume CLI Natural Key

Scope: update `work resume` so the common operator path uses modelo, year, and period flags while preserving exact-id compatibility.

## Description

- Add natural-key `--modelo`, `--year`, and `--period` inputs to `work resume`.
- Add `--revision`, `--select`, `--work-unit-id`, `--calculation-revision-id`, and `--bucket-id` escape hatches for exact or disambiguated resume targets.
- Route the command through `resolve_modelo_workflow_resume_target` from the workflow application facade before calling workflow resume execution.
- Render resolved source, visible filing metadata, short identifiers, and full exact identifiers in command output.

## Outcome

`work resume` now supports natural modelo addressing without requiring operators to copy a workflow run id in the common path, while legacy exact work-unit and workflow-run targets remain available.

## Notes

The CLI module remains a transport consumer: target resolution is delegated to the application workflow facade and workflow execution remains delegated to the workflow application service.
