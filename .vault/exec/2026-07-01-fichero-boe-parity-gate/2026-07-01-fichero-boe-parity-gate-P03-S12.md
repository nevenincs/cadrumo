---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:931fe3e596c75c22266972f25597cafc4669c837a055df82b41357e9402a9540'
step_id: 'S12'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Emit a non-blocking loud coverage advisory Notice when the completeness manifest is absent or manual_extraction

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Compute `completeness_unverified` in `export_modelo_revision` from the export subview (`fixed_width` layout format AND absent completeness manifest), add the field plus a `completeness_advisory_message` property to `ModeloExportResult`.

## Outcome

Landed in commit `d4810b27a`. Implemented at the modelo layer (not `_export.py`, which carried active peer WIP), so the gate's manifest-absent case surfaces a signal rather than implying the export was verified.

## Notes

The advisory rides the typed `Notice` channel, not the result payload, per `cli-notices-are-the-only-diagnostic-channel`.
