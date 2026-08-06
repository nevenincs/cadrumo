---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:4dbcc57a1fae967e50fa10b2e403b2c8057e5c28f25bc703411054362918d444'
step_id: 'S56'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add the storage-management application service exposing read over the declared tree plus a lifecycle-guarded reclaim that refuses on any category whose declared lifecycle forbids deletion, gated by a mutation proof that the refusal fires and a positive control that a prunable category is accepted

## Scope

- `src/cadrumo/application/storage_management/`

## Description

- Add `src/cadrumo/application/storage_management/` exposing a read surface over the declared tree and a lifecycle-guarded `reclaim` that refuses on any category whose lifecycle forbids deletion.

## Outcome

Landed in commit `6ca790e4a7`, an ancestor of the prior reconciliation mark (`bb18425074`, "33 of 64"). The Step's checkbox was missed in that earlier pass despite the code already existing; corrected here.

## Notes
