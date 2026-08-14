---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:43b63a36b925c461d2fbcadc89419c15d2fc210b01b37c4cc9d6e6911c1ad7d3'
step_id: 'S50'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Define the outer-serial harness recipe with explicit membership non-vacuity and exit-status preservation

## Scope

- `justfile`

## Description

- Define a dedicated outer-serial harness recipe with explicit owned modules.
- Preflight each member independently so either empty collection preserves pytest exit 5.
- Run the combined real-process proofs under `-n0` and propagate the failing command status directly.

## Outcome

The installed worker-hook proof and full-corpus collectability proof now have one explicit `test-harness` recipe outside routine unit execution. Each declared member must remain independently non-vacuous before the combined harness verdict runs.

## Notes

Semantic discovery was attempted first, but the local RAG service returned HTTP 500 while degraded. `just --list`, `just --dry-run test-harness`, both individual outer-serial collection preflights, diff integrity, and independent review passed. The full harness run was not used as S50 evidence because broad shared-tree collection currently includes unrelated temporary-tree failures; behavioral membership coverage belongs to S52.
