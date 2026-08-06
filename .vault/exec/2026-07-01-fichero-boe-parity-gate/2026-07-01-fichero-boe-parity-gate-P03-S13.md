---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:49e16d67e474975747aaa7102527d4597debdfb219726f9bf2c02edee61e4911'
step_id: 'S13'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Surface the coverage advisory and propagate the hard parity error on the export_modelo_revision envelope

## Scope

- `src/aeat/application/modelo/_export.py`

## Description

- Emit the coverage advisory on the `modelo export` CLI envelope: add `_completeness_advisory_notice` (WARNING severity, code `modelo.export.completeness_unverified`) and `_export_notices`, which appends it when `result.completeness_unverified`.

## Outcome

Landed in commit `d4810b27a`. Verified by `test_export_completeness_advisory.py` (2 tests): an unverified export emits the advisory notice; a verified/non-fichero-BOE export does not.

## Notes

The hard parity error already propagates naturally as a `FilingExportError` raised inside `export_draft` (before the CLI builds its envelope), so no extra propagation wiring was needed for the panic path.
