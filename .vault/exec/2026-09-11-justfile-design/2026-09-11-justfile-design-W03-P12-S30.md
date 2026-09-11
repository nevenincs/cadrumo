---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:d7e532ed2407f987d50d513d78d49936825c79cfa0cf9d836f184a658363b405'
step_id: 'S30'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Separate release distributions temporary packaging cohorts and infrastructure images

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `M` `dev/packaging/tests/test_preflight_recipe_selection.py`
- `verify:` `just --dry-run build-release build-packaging-cohort build-infrastructure test-packaging-artifacts` -> `pass`
