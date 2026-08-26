---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:e8e85016c0a9742ba80fa468135c5e37e15bccaadf764f5b0ea0784d209921e4'
step_id: 'S124'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Produce the exact clean-commit C0 observation dependency receipt with accepted-parent and rejected-staging provenance, source ancestry, schema and capability inventories, contract digests, validator evidence, and the sole cohort-open disposition

## Scope

- `.vault/reference/2026-08-24-tui-operation-observation-dependency-receipt.md`

## Changes

- `A` `.vault/reference/2026-08-24-tui-operation-observation-dependency-receipt.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tests/test_public_operation_dependency_receipt.py -m integration` -> `pass`
