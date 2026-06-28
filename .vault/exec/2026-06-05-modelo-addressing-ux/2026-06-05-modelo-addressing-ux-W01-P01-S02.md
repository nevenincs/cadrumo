---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S02'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P01.S02 - semantic decomposition discovery

Scope: run semantic discovery for remaining modelo CLI decomposition seams and residual business logic.

## Description

- Verify the `vaultspec-rag` service is running and ready.
- Search the legacy modelo CLI root for decomposition seams, residual calculation behavior, registry authority usage, and private imports.
- Search the workflow-run CLI module for resume exact-id and natural-key migration seams.
- Search the application addressing facade for existing visible-target and revision-selector services.
- Cross-check semantic results with direct `rg` exact discovery over CLI and application surfaces.

## Outcome

`vaultspec-rag` reported a healthy running service on port 8766. Semantic search identified `_resolve_work_unit_for_cli`, `_resolve_revision_for_cli`, `work_calculate`, calculation-result rendering, and filing-record import as important remaining root seams. It also identified `_modelo_work_runs_cli.py` as the resume migration seam: `work_resume` still accepts a positional target resolved by `_resolve_workflow_run_id`, with workflow-run ID as the direct path and 64-character work-unit ID as an exact-id shortcut.

The application-level `src/aeat/application/modelo/_work_addressing.py` facade already contains visible-target work resolution and command-specific revision resolution helpers. That means new CLI slices should consume these services or extend them, not recreate resolver policy in command modules.

## Notes

One broad RAG command with shell-expanded include globs failed before search execution. It was rerun with exact path filters, and no files were changed by the failed command.
