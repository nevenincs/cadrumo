---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:1b474d2ed9a04433f7037c5d706669bb717f019722eabb53fbcc36bf7305f483'
step_id: 'S27'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Make the pytest harness tooling-owned and a prerequisite of the canonical product test aggregate

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --dry-run test-product` -> `pass`
