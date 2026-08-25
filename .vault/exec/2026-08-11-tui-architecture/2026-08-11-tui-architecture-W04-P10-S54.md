---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:03495c1638884d6ab4c141b068e0bcca0b536799ce010cf31a9ca560237669d0'
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

- Focused Ruff and scoped type checks passed for the relocation surface.
- Focused profile and status tests passed: 19 tests; theme and visual verification tests passed: 30 tests.
- Narrow legacy-import census and canonical TUI AST-boundary checks found zero violations; `git diff --check` passed.

## Notes

- The plan step remains open for review. The generic form-rendering flow stays in its existing namespace for its separately planned relocation.
- The full repository hygiene scanner produced no completion output and was not used as an acceptance result.
