---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:b2cb4fec7a7f36adf825406cfd7fbcf154a02243b0c26c6716f18e83d690e848'
step_id: 'S11'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

# Implement the staged root-catalogue resolver with locale fallback rules isolated from production

## Scope

- `dev/registry/migration`

## Description

- Verify the production canonical Modelo identity functions for model, revision, occurrence, continuidad, and alias keys.
- Verify the production fallback order across requested locale and Spanish source.
- Reconcile the historical isolated-resolver row with the live resolver contract.

## Outcome

Resolved in production by `src/cadrumo/domain/calculations/registry/_modelo_localization.py:19-119` and loader enrollment in
`src/cadrumo/domain/calculations/registry/_loader.py:250-329`. The runtime
resolves the requested locale through ordered exact-to-continuidad identities,
then retries the chain in Spanish; no second staged resolver exists.

## Notes

The historical migration resolver was deleted with the disposable application;
this is a reconciliation to the accepted production contract.
