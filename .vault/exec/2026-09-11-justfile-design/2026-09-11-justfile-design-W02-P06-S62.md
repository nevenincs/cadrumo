---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:a085db5bee569c65b6f591ba515ff80027aaa049d4a9aa61548d1e1db8d5bd00'
step_id: 'S62'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Replace the generic modelo and registry-pipeline pass-throughs with authority-specific operations or demote them

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --list` -> `pass`

## Notes

- The legacy generic wrappers remain until W05 completes repository-wide caller migration and removal.
