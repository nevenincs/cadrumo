---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e778d3ce4c53ff48093c4d84de7af2f21f1388dd363615974f3d4021429e5512'
step_id: 'S13'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

# Diagnose the absent Modelo 390 page-02 field at official record position 1628 before re-anchoring the disclosure-split gate, per that gate's own instruction

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/390/`

## Description

- Trace the current Modelo 390 fixed-width authority at official record position 1628 instead of preserving the stale test diagnosis.
- Confirm the 2024 and 2025 page-02 geometry resolves position 1628 to box 34 and page-02-bis offset 353 to box 47.
- Replace only stale explanatory prose in the disclosure-split regression; leave assertions, registry declarations, and layout data unchanged.
- Run the focused disclosure-split, export-extent, design-span, and formatting gates.

## Outcome

The alleged absent field was tracker drift. Both current revisions resolve
`modelo-390-page-02:1628` to box 34 (`iva.anual.total-bases-cuotas-iva`) and
`modelo-390-page-02b:353` to box 47 (`iva.anual.cuota-devengada-total`). Commit
`ebeb4507a3` carries the stale-prose correction. The disclosure-split module passed
5 tests, the export-extent gate passed 2 tests, and the Modelo 390 design-span
selector passed. No registry authority or production code changed.

## Notes

The whole-tree claimed-year layout-design gate remains red for fourteen unrelated
model revisions. That live residue is tracked separately by `P03.S22`; closing this
scoped diagnosis does not close the campaign or claim registry green.
