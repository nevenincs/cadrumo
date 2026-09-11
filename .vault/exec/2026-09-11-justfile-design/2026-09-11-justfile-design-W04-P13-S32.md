---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:287b4a9e0ed1ddefe80a076397f1c8761ebc20ece13392d3cf70c6ca3bdce5e3'
step_id: 'S32'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Rename release readiness preview and rollback-plan recipes without adding release publication authority

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --dry-run release-preview` -> `pass`
