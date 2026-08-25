---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:6e6ab49e9a426f722e7b995f966bbbe3bd2b14389df6ca77d9c4fd70e3f5a67f'
step_id: 'S79'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Remove status-screen imports and project backend status through the CLI surface only

## Scope

- `src/cadrumo/entrypoints/cli/_config/_status_frontend.py`

## Description

- Move status assembly, notices, deadlines, identity, workflow-state, and masking behavior to the public `application.user_profile.status_projection` defining module.
- Migrate the TUI status view and CLI status command to direct defining-module imports.
- Delete the CLI-owned status-screen constructor and its duplicated tests without retaining a facade or shim.

## Outcome

Status projection has one application-owned defining home. The CLI status path is CLI-only and imports no TUI implementation; the TUI imports the same canonical projection directly. Exact review found no scoped re-export, duplicate authority, or compatibility surface.

Independent review approved S79. The combined application/status/TUI gate passed all scoped behavior cases.

## Notes

Broad import-hygiene execution remains affected by concurrent malformed debt and migration-digest work outside S79; scoped behavior and exact ownership evidence are green.
