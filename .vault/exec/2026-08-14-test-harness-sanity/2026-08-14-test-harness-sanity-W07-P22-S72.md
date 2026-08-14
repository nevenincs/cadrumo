---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:d8861130cdeddfaddd40ab92a7b571bfd9bcfdc9f99541c12579d27f8c4edd85'
step_id: 'S72'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Make the repository root the sole collection-policy hook owner

## Scope

- `conftest.py`

## Description

- Run the root collection hook before marker deselection with `tryfirst=True`.
- Apply marker taxonomy before banned-live-import scanning from the repository root.
- Preserve the valid pytest hook signature and transitional idempotence while the child hook still exists.

## Outcome

Every collected test subtree now reaches the shared banned-live-import policy from the repository root before the default unit selector can hide live items. The root hook is ready to become the sole policy owner when S73 removes the child delegation.

## Notes

A temporary real domain-local live module importing `unittest` exited collection with status 2 under the default selector, then was removed. The focused serial enforcement tests passed two cases, Ruff and diff integrity passed, and independent review found no hook-ordering or plugin regression. Durable subprocess coverage remains assigned to S74.
