---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S07'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W02.P02.S07` step record

Scope: `W02.P02.S07` - Render an Evidencia tab in the offline xls workbook from the evidence facet.

## Description

- Add an offline openpyxl workbook materializer for `SheetExportPlan`.
- Add the fixed `Evidencia` tab to the shared tab enumeration.
- Render contributor and manual-basis evidence rows from `SheetExportPlan.evidence`.
- Cover XLSX serialization and readback of the evidence tab, value cells, and formula cells.

## Outcome

The calc-sheets plan can now be materialized as an offline workbook that includes a protected `Evidencia` tab bound to the typed evidence facet.

## Notes

The planned path `src/aeat/application/ledger/_workbook_export.py` does not exist in the current codebase. The implementation lands beside the shared `SheetExportPlan` records in `src/aeat/application/storage/calc_sheets/_workbook_export.py`, which is the current calc-sheets application boundary consumed by both offline and online transports.
