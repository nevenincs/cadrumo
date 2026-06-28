---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S23'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W05.P06.S23` step record

Scope: `W05.P06.S23` - Offline/online evidence-identical assertion.

## Description

- Add a shared `evidence_table` projection for the `Evidencia` surface.
- Use the shared projection from the online Google Sheets apply adapter.
- Assert the online evidence value writes match the offline workbook evidence cells for the same plan.

## Outcome

The `Evidencia` surface is now tested for offline/online identity through a single shared projection.

## Notes

Recorded after landed commit `81f4ceeb1`. This record covers the evidence-identical assertion only; S22 was reopened because number formats and start/final anchors are not yet rendered.
