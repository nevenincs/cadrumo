---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-07-17'
body_hash: 'sha256:48c3a3a7c5c9286904889e850363fb2ea6cb48d8ce011ff3b598c7397a6c7890'
step_id: 'S06'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W02.P02.S06` step record

Scope: `W02.P02.S06` - SheetExportPlan evidence facet.

## Description

- Add typed `SheetEvidenceContributorRow`, `SheetEvidenceManualEntry`, and `SheetEvidenceFacet` records.
- Add an `evidence` facet to `SheetExportPlan` with an empty default.
- Cover JSON roundtrip, default empty evidence, and snapshot-fingerprint validation.

## Outcome

The calc-sheets plan model can now carry per-casilla ledger contributors and manual basis entries without renderer-specific structure.

## Notes

Rendering the `Evidencia` workbook tab remains tracked in S07. Sidecar emission remains tracked in S08.
