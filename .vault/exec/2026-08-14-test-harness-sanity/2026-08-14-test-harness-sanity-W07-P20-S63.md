---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:b8cf94eb38fbac27ef96bba9fea07bb56cd8ee6b660d892d3d6feae941414012'
step_id: 'S63'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Canonicalize the M180 committed registry snapshot family

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Replace two identical M180 committed-snapshot fixtures with one registry-test conftest owner.
- Preserve function scope, non-autouse behavior, registry authority dependency, and snapshot lifecycle.
- Keep the canonical M130 owner and all M100 snapshot families unchanged.

## Outcome

Both formula-runtime consumers now resolve `committed_modelo_180_snapshot` from their narrowest common conftest, leaving one definition for the M180 family without altering adjacent registry fixture ownership.

## Notes

All 23 focused tests collect, one representative validation test passes, and fixture discovery plus function cadence are correct. Previous-filing setup is blocked because the current M180 revision is `pending_review` while filing-grade snapshots require operator review; the unchanged helper correctly refuses it. Ruff, diff integrity, family isolation, and independent review passed. The manifest will refresh with the remaining registry-family steps.
