---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:632ebabcf2828d8985ed8f2d7a7eccdf69b98a5d666bbb9b998c6b1f22289fa0'
step_id: 'S61'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Pin the config storage surface through the real command tree rather than by calling handlers directly, gated by the documented-command conformance suite resolving every cited verb against the live CLI

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/`

## Description

- Pin the `config storage` surface through the real command tree (not direct handler calls) in the documented-command conformance suite.

## Outcome

Landed in commit `672c88cf43`, an ancestor of `bb18425074`; checkbox corrected here.

## Notes
