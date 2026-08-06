---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:fc40f9b30a4a9be16b6258b8689300f54df3f3f0af62a0947a1cffbc0a8f22b7'
step_id: 'S22'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W05.P06.S22` step record

Scope: `W05.P06.S22` - Sheets apply renders number formats + start/final + Evidencia identically to the offline xls.

## Description

- Add Google Sheets repeatCell requests for `SheetNumberFormat` facets.
- Add Google Sheets repeatCell emphasis requests for section headers and start/final anchors.
- Keep `Evidencia` value rendering on the shared evidence projection used by the offline workbook.
- Cover number-format and emphasis requests in the offline/online conformance tests.

## Outcome

The online apply adapter now renders numeric display formats, presentation emphasis, and the evidence value surface from the same plan facets the offline workbook consumes.

## Notes

Recorded after landed commit `ceddb187c`.
