---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:cdc63b12a226e0ddc0a6df98cb9371197eafdb389f0f0cbc0897b7451c59f3ba'
step_id: 'S54'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Expose generated-tree and runtime-authority currency as delegated status facts without recomputation

## Scope

- `dev/registry/analysis/generated_tree_state.py`

## Changes

- `A` `dev/registry/analysis/registry_status.py`
- `M` `dev/registry/analysis/generated_tree_state.py`
- `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `M` `dev/registry/pipeline/cli.py`
- `verify:` `just --dry-run report-registry-generated-state` -> `pass`
