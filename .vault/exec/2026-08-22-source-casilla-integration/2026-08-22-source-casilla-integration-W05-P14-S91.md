---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:a07cf8aab9caf48af0a39a12eb69d2cdcfda34f9adbc3a2ae451fe39b10c30cd'
step_id: 'S91'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# prove a real worksheet export-pull-calculate encrypted revision round trip

## Scope

- `src/cadrumo/application/aggregation/_foreign_assets.py`
- `src/cadrumo/application/modelo/_calculation_actions.py`
- `src/cadrumo/application/storage/calc_sheets/_styling.py`
- `src/cadrumo/application/storage/calc_sheets/tests/test_row_set_calculation_roundtrip.py`

## Description

- Route S90 `Modelo720RowObservation` values through the existing Modelo 720 source resolver and existing bucket calculation action.
- Retain the registry selector grouping, binding and row coordinates, worksheet source identity, and canonical content fingerprint in the established source-mesh and encrypted revision carriers.
- Guard empty calculation and provenance worksheet bodies so the canonical local exporter remains valid without fabricated rows.
- Exercise the actual XLSX serializer, existing Google pull decoder, S90 ingress boundary, M720 calculation path, and encrypted calculation repository without a mock or network substitute.

## Outcome

The real worksheet round trip retains `per_foreign_asset`, every resolved row-binding coordinate, `detalle:per_foreign_asset:row-1`, and the row fingerprint after encrypted repository read-back. The calculation and persistence route remains the pre-existing M720 resolver, source mesh, and calculation revision repository.

## Notes

The M720 handoff implementation was captured by concurrent shared-worktree commit `2b8164c1ae`; this Step retains that mixed provenance without rewriting history. The scoped follow-on contains the real round-trip regression, empty-export guards, execution record, plan closure, and feature index only.
