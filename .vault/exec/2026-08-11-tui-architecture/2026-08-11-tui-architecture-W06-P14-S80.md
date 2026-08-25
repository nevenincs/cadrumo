---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:70bb952af5366089cde81f1464a2afb6e560643c4c90f88a8ac4cc317735ce35'
step_id: 'S80'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Replace profile-bundle TUI imports with application flow and operation facades

## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_bundle_flow.py`

## Description

- Delete the former profile-bundle flow and its export/import command registrations rather than migrating a dead frontend.
- Retain the canonical profile archive-export and restore commands as the sole transfer surfaces.
- Add a live command-graph gate proving both retired profile-root leaves neither resolve nor register.
- Prove the surviving archive-export and restore leaves resolve to their authored schema identities.

## Outcome

S80 is closed as retired and superseded, not as a migrated implementation. The former profile-bundle TUI consumer and its command leaves are absent, while the current archive-export and restore commands remain authoritative.

The focused command-graph suite passes nine cases. Independent review approved the exact deletion and negative-registration evidence with no shim, re-export, or compatibility path.

## Notes

The obsolete implementation was deleted in `c4732174186`. The closure gate intentionally fails if either retired leaf re-enters the graph or registration metadata.
