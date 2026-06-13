---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S08'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W02.P02.S08` step record

Scope: `W02.P02.S08` - Emit a machine-readable evidence sidecar alongside the exported artefact.

## Description

- Add strict sidecar and offline export result records for calc-sheets workbook exports.
- Serialize sidecar JSON canonically from `SheetExportPlan.metadata` and `SheetExportPlan.evidence`.
- Bind the sidecar to the workbook payload with the actual XLSX SHA-256.
- Cover sidecar JSON readback, media types, hashes, metadata, contributor rows, and manual basis entries.

## Outcome

Offline calc-sheets export can now emit both the workbook bytes and an adjacent machine-readable evidence sidecar from the same shared plan.

## Notes

The planned path `src/aeat/application/ledger/_workbook_export.py` remains absent in the current codebase. The sidecar implementation stays in the calc-sheets application package beside the S07 offline workbook materializer.
