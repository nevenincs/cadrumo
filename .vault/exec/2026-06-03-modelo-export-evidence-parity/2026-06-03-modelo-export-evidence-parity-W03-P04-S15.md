---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S15'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W03.P04.S15` step record

Scope: `W03.P04.S15` - Assert every computed casilla carries a live spreadsheet formula.

## Description

- Add a registry-grounded assertion over every covered snapshot's computed casillas.
- Compare computed casilla ids against `SheetExportPlan.formula_cells`.
- Fail with exact computed casilla ids that lack a live workbook formula.

## Outcome

Covered modelos cannot silently expose computed registry casillas as inert or missing workbook cells.

## Notes

Recorded after landed commit `db1f5e593`, which introduced the live-formula parity gate.
