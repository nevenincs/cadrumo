---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f394a061a13691bd60016423c96e5f2e05a8d250b0f5515003857ca361f823de'
step_id: 'S47'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Relocate terminal theme and styling primitives without carrying application state

## Scope

- `src/cadrumo/entrypoints/tui/components/theme.py`

## Description

- Move the terminal palette, CSS tokens, appearance helpers, and notice widget
  implementation into the canonical components theme module.
- Remove the legacy theme module and update all affected TUI, development, and
  test consumers to the canonical components facade.
- Remove moved theme symbols from the legacy inbound-TUI facade.
- Keep theme installation presentation-only by using neutral `AUTO` resolution
  when the caller does not provide an appearance.

## Outcome

Focused theme tests pass (30 tests), and the focused form, status, and visual
verification lane passes (23 selected tests). Ruff and ty checks pass for all
owned changed modules. Exact census confirms no Python imports of the deleted
legacy theme module and no moved-symbol imports from the legacy facade; the
legacy theme source is absent and the components tree contains no S48 widget
module yet.

## Notes

The broader flow lane is not used as a S47 gate because it contains unrelated
existing lifecycle and inventory failures in the shared worktree. S48 remains
unstarted. The S47 plan checkbox is intentionally left open pending independent
review.
