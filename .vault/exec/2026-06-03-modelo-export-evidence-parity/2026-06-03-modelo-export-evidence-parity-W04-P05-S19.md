---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S19'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W04.P05.S19` step record

Scope: `W04.P05.S19` - Enroll M100 (renta) into evidence-bundling + parity.

## Description

- Add layout support for date-binding cells referenced by formulas.
- Translate the registry `age_at_year_end` operation into a workbook formula anchored to the date-binding cell and filing year.
- Move M100 from the explicit translation-gap witness into the registry-grounded parity coverage list.

## Outcome

M100 now builds through `build_export_plan` and participates in the offline parity gate that checks completeness-manifest casilla coverage and live formula coverage.

## Notes

The S19 implementation keeps the date-binding support generic. It reserves `Entradas` cells for formula-referenced date bindings and avoids any M100-only branch in the engine or translator.
