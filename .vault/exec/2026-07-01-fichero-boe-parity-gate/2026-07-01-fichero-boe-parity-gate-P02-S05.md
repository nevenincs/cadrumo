---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-08'
step_id: 'S05'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Add a helper for the manifest required set restricted to casillas representable in an applicable non-suppressed record, carrying number, segmento and record-order metadata

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Make `boe_representable_casilla_ids` disposition-aware by skipping records suppressed for the draft's disposition (`_did_page_suppressed`, e.g. the DID refund page on a non-refund filing), so the applicable-required set the gate computes as `manifest ∩ representable` excludes casillas that legitimately do not render for this filing.

## Outcome

Landed with S04/S06/S07 in the P02 commit. The applicable restriction is carried by the representable helper's suppression pass rather than a separate function.

## Notes

The manifest carries `number`/`segmento` metadata per casilla for the P03 structural-fidelity assertion; record-order metadata comes from the layout's `ExportRecordDefinition.order`.
