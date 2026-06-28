---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S25'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
---

# W04.P07.S25 resume interface contract

Scope:
- `src/aeat/application/workflow/_resume.py`
- `src/aeat/entrypoints/cli/_modelo_work_runs_cli.py`
- `src/aeat/application/modelo/_work_addressing.py`

## Contract

`modelo work resume` must become a natural-key command for the common operator path while preserving exact identifiers as advanced compatibility:

- Normal path: active bucket/profile plus `--modelo`, `--year`, and `--period` selects the visible filing target.
- Optional registry revision selection may be accepted only as the existing registry-revision disambiguator for work-unit selection; it is not a new workflow selector axis.
- Legacy exact workflow run id remains valid for direct resume of a known persisted run.
- Legacy exact work-unit id remains valid and resolves to the newest persisted workflow run for that work unit's workflow period.
- The command remains local and read-only: it validates resume preconditions and emits resumable context, but does not contact AEAT and does not write bucket events.
- Visible target resolution must use the centralized modelo application addressing facade, not local CLI selector branching.
- Exact work-unit resolution must use the centralized modelo addressing facade or shared exact-id validator; the CLI must not maintain a second raw-id policy.
- Once a work unit is resolved, workflow lookup derives `workflow_period_for_work_unit(unit)` and calls the existing workflow-layer run lookup/resume gate.
- Workflow run id lookup remains exact: a 16-character run id is already the workflow system's persisted run key.

## Current State

- `_modelo_work_runs_cli.py` currently accepts a required positional `target` and describes the normal path as a workflow run id or 64-character work-unit id.
- `_resolve_workflow_run_id` currently owns local regexes for both run ids and work-unit ids.
- Exact work-unit id lookup currently calls `get_work_unit`, derives `workflow_period_for_work_unit(unit)`, then calls `find_latest_run_for_period`.
- `find_latest_run_for_period` already resolves newest persisted run for `(modelo, workflow_period)`.
- `resume_modelo_workflow` already applies the resumability rules over an exact run id.

## Required Follow-Up

- Add natural-key CLI flags to `work resume`.
- Route modelo/year/period/exact-work-unit resolution through `aeat.application.modelo` centralized addressing exports.
- Keep exact workflow run id support as direct workflow-layer lookup.
- Render ambiguous visible filing target refusals with candidate guidance from the modelo selector boundary.

## Evidence

- `vaultspec-rag` code search for `work resume legacy id lookup modelo year period natural key workflow run` returned `_resume.py` `find_latest_run_for_period`, `resume_modelo_workflow`, and current resume locale/help surfaces.
- Direct `rg` inventory confirmed `_modelo_work_runs_cli.py` is the only current CLI owner of resume target parsing.

