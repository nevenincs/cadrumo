---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d1e33e80c5a7f8b4b021a345c4e011b85bbba4fc4c624fd53fd5a46c3064d34a'
step_id: 'S87'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Move remaining development TUI launchers and surface checks beneath the canonical TUI devtools package

## Scope

- `dev/tui`

## Description

- Delete the retired `dev/tui` tree and move fixture, frame, journal, replay, and surface definitions into public TUI devtools modules.
- Import every consumer directly from its defining module while leaving the devtools package initializer inert.
- Enforce exact public exports, single definition sites, canonical import edges, and repository-wide rejection of private, facade, unknown, and constant dynamic-import reaches.

## Outcome

Development TUI tooling now has one public canonical home per reusable module. The retired tree and underscore-private predecessors are absent, with no compatibility layer, shim, or re-export. Ruff passed and the focused integration gates passed; an independent architecture review approved the hardened global proof.

## Notes

The package namespace remains intentionally inert; public means directly importable defining modules, not a package facade.
