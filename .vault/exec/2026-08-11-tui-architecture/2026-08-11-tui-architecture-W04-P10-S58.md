---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1f21899ac159763470d692c4d42394887f411de900d97520583b776c4e33369f'
step_id: 'S58'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Move presentation tests under the canonical owning packages and remove backend imports of TUI test helpers

## Scope

- `src/cadrumo/entrypoints/tui/tests`

## Description

- Hard-move presentation tests from the retired inbound-adapter package to their canonical TUI owning packages.
- Move the manager pilot helper to `entrypoints.tui.tests.manager_pilot` and migrate all six consumers to local direct imports.
- Delete the complete tracked legacy TUI test package without a shim, re-export, or compatibility initializer.
- Prove zero backend imports of canonical TUI test helpers and zero remaining tracked legacy TUI files.

## Outcome

Presentation tests and their reusable pilot helper now have only canonical TUI homes. No backend module imports a TUI test helper, all TUI package initializers are inert, and the retired inbound TUI tree contains no tracked or physical residue.

Independent review approved S58. The landed relocation is commit `0acec93b1a0`; exact source and import censuses are empty for the retired homes and backend helper reaches.

## Notes

The remaining CLI censo Textual pilot follows the still-live S77 production frontend path and is owned by S77, not by presentation-test relocation. The stale exact-count migration test is owned by S88 terminal-manifest closure; the live migration census is correctly empty.
