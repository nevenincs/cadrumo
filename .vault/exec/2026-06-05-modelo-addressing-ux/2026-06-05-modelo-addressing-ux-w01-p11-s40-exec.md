---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S40'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P11.S40 resolver duplication inventory

Scope:
- `rg resolver duplication inventory`

## Description

- Confirm `vaultspec-rag` service health before semantic discovery.
- Run semantic code search for modelo work addressing, calculation revision selection, exact-id routing, and resume lookup.
- Run exact searches for work-unit IDs, calculation-revision IDs, workflow-run IDs, raw exact-id regexes, and resolver helpers across modelo application, workflow application, CLI modules, locales, and docs.
- Read the active addressing and resume hotspots directly.

## Outcome

The current codebase already contains a partial centralized application surface in `src/aeat/application/modelo/_work_addressing.py`, exported through `src/aeat/application/modelo/__init__.py`. It centralizes `ModeloWorkAddress`, visible-target work resolution, exact work-unit lookup, calculation-revision selection, and command-specific verifiable, fileable, and exportable revision resolution.

The remaining duplication is concrete:

- `src/aeat/entrypoints/cli/_modelo_work_runs_cli.py` still defines local workflow-run and work-unit regexes, accepts a positional target, resolves 64-character work-unit IDs through `get_work_unit`, converts them through `workflow_period_for_work_unit`, and calls `find_latest_run_for_period`.
- `src/aeat/application/workflow/_resume.py` still owns resume discovery only by workflow period or exact run ID; it does not accept a modelo work address or delegate visible-target resolution through the modelo addressing facade.
- `src/aeat/entrypoints/cli/_modelo_cli_support.py` still owns raw 64-character exact-id validators for work-unit and calculation-revision IDs. This can remain as transport validation only if future guards prevent selector policy from moving there.
- `src/aeat/entrypoints/cli/_modelo.py` still contains legacy resolver helpers and ID-heavy command bodies in the old root alongside extracted modules, which makes it a residual migration and guard target.
- `src/aeat/entrypoints/cli/_modelo_export_cli.py` already consumes addressing helpers but remains a useful compatibility check because it still exposes exact work-unit and calculation-revision inputs.
- Locale and docs searches still show explicit `work_unit_id`, `calculation_revision_id`, and `work resume` ID guidance. The clearest stale common-path text is the resume help that says it accepts workflow run IDs or work-unit IDs, with no modelo/year/period path.

## Notes

- The first two semantic searches with include globs failed because PowerShell expanded the glob arguments before `vaultspec-rag` received them. The successful semantic search was rerun without include filters against the running service on port 8766.
- No source code was changed in this step.
