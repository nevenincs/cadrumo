---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S11'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W03.P03.S11` step record

Scope: `W03.P03.S11` - Number-format plan facet by CasillaDefinition.data_type.

## Description

- Add a strict `SheetNumberFormat` plan record carrying cell address, casilla id, format kind, and renderer pattern.
- Derive number-format facets from registry casilla `data_type` for money, integer, and ratio-as-percentage casillas.
- Add a registry-grounded parity regression asserting every covered modelo's numeric casillas carry the expected format facet.

## Outcome

`SheetExportPlan` now carries renderer-neutral number-format directives for numeric casillas, ready for the offline and online renderers to consume in later steps.

## Notes

This step intentionally adds the shared plan facet only. Applying the formats to XLSX and Google Sheets is left to the renderer parity steps.
