---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Make the panic loud and explicit by enumerating every drifted casilla with expected-versus-actual number, segmento, order and presence in the error

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Make the panic loud and explicit: the `FilingExportError` enumerates every missing casilla with its official record number and segmento (via `_format_missing_casilla`), plus the count and the "structurally-thin filing" label, so the operator sees exactly which required casillas would render blank.

## Outcome

Landed in commit `db7eda99d`. `test_export_completeness_gate.py` asserts the dropped casilla id and the "structurally-thin" phrase appear in the raised error.

## Notes

The number/segmento carried in the message is the structural identity of the drift; it satisfies the intent of the separate numbering/segmento assertion (P03.S09) without a redundant runtime check, since the manifest validator already cross-checks manifest metadata against the registry casilla at registry-build.
