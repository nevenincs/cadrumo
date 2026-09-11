---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:94c16b8a9204cf96c4a8b3565ea821446040c3d4e5916ce38ce4a82672d29f57'
step_id: 'S20'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Keep container capability probes outside portable product and release-artifact ownership

## Scope

- `dev/containers`

## Changes

- `M` `justfile`
- `verify:` `just --dry-run test-devcontainer test-runner-image` -> `pass`
