---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S13'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W03.P03.S13` step record

Scope: `W03.P03.S13` - Explicit labelled start and final anchor cells.

## Description

- Add the typed `SheetAnchor` facet to `SheetExportPlan`.
- Emit an `Entradas` start anchor and a `Cálculos` final/result anchor.
- Include anchor labels in the plan value-cell payload so both transports write them as real cells.
- Render anchors as bold in the offline workbook and cover the behavior with formatting tests.

## Outcome

Workbook plans now expose explicit start and final/result anchors that orient the input-to-result flow without relying on implicit row position.

## Notes

Recorded after landed commit `e725047b5`.
