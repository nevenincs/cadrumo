---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:abb2f9d883d22a0cdaff524fca42556bb9bf1f061a87821e06504d3e4030cd63'
step_id: 'S24'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Register modelo.work.select and the sole C1 modelo.work.review destination over the architecture-relocated view, consuming the exact public ModeloWorkReview without a second producer or legacy route

## Scope

- `src/cadrumo/entrypoints/tui/modelo/view`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/view/work_select.py`
- `A` `src/cadrumo/entrypoints/cli/_modelo_work_select_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_work_review_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_work_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `M` `dev/quality/modelo_workspace_action_denominator.py`
- `M` `.vault/reference/2026-08-24-tui-modelo-workspace-action-denominator-reference.md`
- `verify:` `uv run --no-sync ty check` (all touched files) -> `pass`

## Notes

`modelo.work.review` and the new `modelo.work.select` are both flipped to
`TuiCapability.AVAILABLE`; `work_review()` and `work_select()` branch on
`tui_was_requested(ctx)` and launch the real `ModeloWorkReviewApp` /
`ModeloWorkSelectApp` Textual hosts, then still emit the normal JSON/text
envelope afterward so the CLI contract stays uniform in both modes. The
select screen is a pure projection over an already-resolved
`tuple[WorkUnit, ...]` (no repository or catalogue access of its own),
mirroring how `ModeloWorkReviewScreen` only renders an already-built
`ModeloWorkReview`. The action denominator (`dev/quality/modelo_workspace_action_denominator.py`)
required a new closed-table row for `modelo.work.select`, added and
regenerated in this Step rather than left to drift.
