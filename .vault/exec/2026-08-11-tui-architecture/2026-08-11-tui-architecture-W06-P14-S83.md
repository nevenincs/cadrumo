---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:83c45b28cb527b8202adabd0860c8f83df79cc02dac92da77a115be3f3430409'
step_id: 'S83'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Remove work-wizard imports of TUI internals while preserving line-mode and installed-TUI selection semantics

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py`

## Description

- Remove CLI imports, selectors, and dynamic construction of TUI internals.
- Retain the application-owned `LineFlowFrontend` line-mode path.
- Declare `TuiCapability.NOT_IMPLEMENTED` explicitly and enforce it before command preconditions.
- Preserve the literal `modelo.work.wizard` identity across result, rendering, envelope, and refusal contracts.
- Route output through canonical `emit_envelope` without alias or shim.

## Outcome

The work wizard is a CLI-only line-mode projection. TUI requests refuse through the shared command policy before authentication or handler resolution, and the module has no TUI or Textual dependency.

Independent review approved the row. Focused Ruff passed; the global TUI policy suite passed 17 tests, migration/import-linter gates passed 15 tests, and the work-wizard line-mode suite passed 12 tests.

## Notes

Five broader combined-wizard failures occur in unrelated Modelo 303 external-filing fixture setup before this handler is reached; they do not alter the focused green evidence.
