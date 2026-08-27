---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:a95580044dcf939336571f8ff02b87583234edad662085131793e4a8c8bd4bcb'
step_id: 'S295'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Establish whether modelo 210 annual grouped-renta rows are correctly represented in what is exported, given the module states the rows are accepted for legal evidence and validation only and are never summed into an input or computed casilla: confirm the scalar casillas the export record does carry represent the homogeneous group faithfully, or establish that the annual aggregate is under-computed, and record which

## Scope

- `src/cadrumo/application/modelo/_m210_agrupacion_renta.py`
- `the modelo 210 annual export record and its casillas`
- `and a grounded multi-row M210 annual worked example`

## Changes

- `A` `.vault/audit/2026-08-27-tui-architecture-modelo-210-annual-grouped-renta-export-fidelity-determination-audit.md`
- `verify:` `test_annual_grouped_rentas_persist_without_becoming_a_second_arithmetic_path` (existing, already-shipped) -> `pass`

## Notes

Determination Step, no production code changed. Determination: no defect. Full
evidentiary chain recorded in the linked audit document -- module docstring,
`2026-07-10-m210-irnr-phase-2-engine-adr` ruling, the `base_imponible_directa_i`
manual `input_kind` registry declaration, the existing e2e worked example, and
the `0001-record-m210-autoliquidacion.toml:1290` scalar export field.
