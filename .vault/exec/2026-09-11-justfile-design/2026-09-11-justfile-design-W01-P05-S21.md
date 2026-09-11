---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:7f4c2f313b0e6a36362db3fc5683359cf5edf415210b6914bd112ba962d43619'
step_id: 'S21'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Replace bootstrap setup and doctor recipes with minimal convergence optional provisioning and read-only diagnosis

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --dry-run setup` -> `pass`
- `verify:` `just --dry-run setup-check` -> `pass`
- `verify:` `just --dry-run doctor-dev` -> `pass`
- `verify:` `just --dry-run doctor-product` -> `pass`
- `verify:` `just --dry-run doctor-python` -> `pass`
- `verify:` `just --dry-run doctor-browser` -> `pass`
