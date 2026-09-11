---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:98c74d79e793d887a86c08a5ab7434fec3ab0e8df21e84e2797b1ac3f70a5af4'
step_id: 'S64'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Replace database migration creation and upgrade with separately named mutation recipes

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --dry-run db-migration-create "synthetic local check"` -> `pass`

## Notes

- `uv run --no-sync alembic --help` -> `fail` (pre-existing missing Alembic command; no database upgrade executed)
