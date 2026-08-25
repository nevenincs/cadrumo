---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:fe19bbfb9547740eee9c77bc290c989bc5f9258ae8eeb84e9d6e3e6239963e6c'
step_id: 'S54'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Relocate profile overview, editor, status, and task projections without changing profile policy

## Scope

- `src/cadrumo/entrypoints/tui/profile`

## Description

- Relocate the profile overview, editor, and status Textual projections into the canonical TUI profile namespace.
- Extract manager-action presentation contracts into the canonical task projection module.
- Repoint TUI, CLI, development, and test consumers to direct canonical imports, then remove the legacy modules and exports.

## Outcome

- Independent review approved S54 for closure.
- Focused Ruff and scoped type checks passed for the relocation surface.
- Focused profile and status tests passed: 19 tests; theme and visual verification tests passed: 30 tests.
- Narrow legacy-import census and canonical TUI AST-boundary checks found zero violations; `git diff --check` passed.

## Notes

- The generic form-rendering flow stays in its existing namespace for its separately planned relocation.
- The full repository hygiene scanner produced no completion output and was not used as an acceptance result.
- Unrelated shared-worktree WIP in custody, registry, documentation, and test surfaces was neither staged nor modified for S54 closure.
