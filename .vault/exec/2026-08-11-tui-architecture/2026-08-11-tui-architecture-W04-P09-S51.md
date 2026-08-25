---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b1bad72bc69a12a89a6ed48130c92c1bbd92ae5b19e602194399f8b6a2ac1e73'
step_id: 'S51'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Relocate status and busy presentation so it renders supplied operation state rather than owning timers or work

## Scope

- `src/cadrumo/entrypoints/tui/components/status.py`

## Description

- Move `PinnedStatusBar` and `StatusTone` from the legacy inbound TUI package to `entrypoints.tui.components.status`.
- Remove countdown ownership and require callers to supply their already-rendered progress state.
- Update every production and test consumer to import the canonical component directly; remove the legacy facade exports.
- Add a canonical Textual pilot proving pinned rendering, tone, literal text, redaction, empty collapse, and exact supplied progress presentation.

## Outcome

The reusable status channel is now an inert presentation component. It owns no timer, task, worker, operation, application state, or lifecycle authority. `ProfileManagerApp` renders `OperatorProgress` before handing the text to the component, keeping countdown policy outside the presentation primitive. The components facade remains inert.

Commit `4efd6f22c2` (`relocation: status presentation`) contains the relocation and direct imports. Independent review approved the completed step.

Verification passed: the canonical Textual status suite (5 tests), scoped collection (64 tests), Ruff check and format, ty, exact legacy/timer censuses, and scoped diff check.

## Notes

Focused legacy-consumer integrations also exposed pre-existing failures outside this relocation: authentication refusals surfaced through `WorkerFailed`, independent persistence/session prerequisites were missing, and a recovery-screen confirmation control was unavailable. Full collection was independently blocked by a missing CLI `missing_binding_guidance` import. None was changed in this presentation-only step.
