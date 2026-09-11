---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:c34c0b622dfe3bd80bef29ecd639454ffaf2c38dc39e3d23dfea9bd7f32d4c6e'
step_id: 'S59'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Expose the exact approved setup and doctor recipe manifest

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --list` -> `pass`
- `verify:` `just --dry-run setup` -> `pass`
- `verify:` `just --dry-run setup-check` -> `pass`
- `verify:` `just --dry-run doctor-dev` -> `pass`
- `verify:` `just --dry-run doctor-product` -> `pass`
- `verify:` `just --dry-run doctor-python` -> `pass`
- `verify:` `just --dry-run doctor-browser` -> `pass`
