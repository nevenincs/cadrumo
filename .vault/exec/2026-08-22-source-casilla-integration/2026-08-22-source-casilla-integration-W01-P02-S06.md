---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:b9355d58b12e3a9fc49f79bd6c48d93e136f0c56e35429f04a7ada53640fdaa6'
step_id: 'S06'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# derive registry destination records from validated revision snapshots

## Scope

- `src/cadrumo/application/registry/source_connectivity.py`

## Description

- Project every casilla from the filing-authoritative validated snapshot.
- Preserve canonical modelo, revision, and casilla identities plus authored declaration facts.
- Order rows by canonical casilla id so fragment order cannot affect the census.
- Export the projection through the application registry facade.

## Outcome

The registry-side census now has a deterministic destination record for every casilla in a selected revision. The projection does not reimplement the existing producer inventory or infer equivalence from box numbers or labels.

## Notes

Vaultspec RAG and regex sentinels found the existing `ModeloRevision.producer_inventory()` authority. This step therefore remains a thin snapshot projection. Ruff passed, imports passed, and a real Modelo 100 2024 snapshot produced 2,103 records with exact cardinality, canonical ordering, and matching modelo/revision identity.
