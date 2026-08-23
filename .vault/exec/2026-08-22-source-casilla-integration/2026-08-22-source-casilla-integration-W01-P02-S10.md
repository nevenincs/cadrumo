---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d45ea2d53b83b24ffa104e2cf58a677756ca3d4b1d7250c389f618162ef3884e'
step_id: 'S10'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# verify all loaded modelo revisions produce deterministic registry-side census records

## Scope

- `src/cadrumo/application/registry/tests/test_source_connectivity_inventory.py`

## Description

- Build an applicability-grade validated snapshot for every loaded modelo revision.
- Project every destination, binding, formula, relation, and used source disposition twice.
- Assert stable equality, declaration cardinality, canonical ordering, and complete revision coverage.

## Outcome

Every loaded revision now proves that the registry-side census is deterministic and lossless at the declaration-family boundary, including revisions that truthfully lack filing capability.

## Notes

The first parallel run hit the repository's known loader-cache/share crash before executing. The required sequential rerun exposed that filing-grade snapshots correctly refuse applicability-only Modelo 036; the gate was corrected to request the typed applicability authority rung rather than weakening filing checks. Ruff passed and the sequential corpus gate passed.
