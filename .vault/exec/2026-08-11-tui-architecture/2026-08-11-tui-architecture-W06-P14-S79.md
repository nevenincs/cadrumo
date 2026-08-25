---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:fee53b5d9fb41e84ff3460d73b36e132e37cb276325b81c418cf40309537ab68'
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
