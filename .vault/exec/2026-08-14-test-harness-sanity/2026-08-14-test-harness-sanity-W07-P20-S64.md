---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:01030b2c8d348c6e617e983cc1de0299b276c3f772a9aa4cc31500bf2693fcd0'
step_id: 'S64'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Canonicalize the M100 2024 committed registry snapshot family

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Replace five identical M100 2024 committed-snapshot fixtures with one registry-test conftest owner.
- Preserve function scope, non-autouse behavior, registry authority dependency, and snapshot lifecycle.
- Keep the module-scoped explicit-revision rental fixture and the M130/M180 owners unchanged.

## Outcome

Five M100 consumers now resolve their common filing-grade snapshot from the narrowest registry-test conftest. The rental-law surface retains its distinct module cadence and explicit revision selection.

## Notes

All 63 focused tests collect, fixture discovery distinguishes canonical and rental owners correctly, and Ruff, diff integrity, family isolation, and independent review passed. Current M100 registry data remains `pending_review`, so filing-grade behavior setup is externally blocked at the unchanged authority gate. The manifest will refresh after the M200 dev-registry slice settles.
