---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:649a4e730dfd4db86089197eee02ce499ab870ee536b1af735df04ba371fa968'
step_id: 'S12'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Expose read-only registry status across validity targets authority publication and runtime loadability

## Scope

- `dev/registry/analysis`

## Changes

- `A` `dev/registry/analysis/registry_status.py`
- `M` `dev/registry/analysis/generated_tree_state.py`
- `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `M` `dev/registry/conformance/cli.py`
- `M` `dev/registry/pipeline/cli.py`
- `verify:` `just --dry-run report-registry-status` -> `pass`

## Notes

- Live status reports 95 generated targets as unreadable because the canonical owner could not re-render them; exclusions remain fail-visible.
