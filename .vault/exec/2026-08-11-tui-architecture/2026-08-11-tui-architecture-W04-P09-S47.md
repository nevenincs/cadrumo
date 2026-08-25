---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:61ca6a66e01f2c0205699f5141478d6133931d2496c8d703c2d9a2aed016dae1'
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

Independent review rejected component-symbol republication from the package
initializer. The corrective pass made `components/__init__.py` inert with an
empty typed export set and moved all consumers to the direct canonical theme
module; no compatibility facade or alias remains.

Independent review approved S47. The unrelated broader-flow failures remain
classified as shared-worktree inventory/lifecycle failures and are not part of
this step's gate. S47 is closed in the plan; S48 is the next open step.
