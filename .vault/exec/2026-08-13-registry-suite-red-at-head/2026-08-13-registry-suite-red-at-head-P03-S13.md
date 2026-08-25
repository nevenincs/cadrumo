---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:c76edaedeb7b663cf80a02c6bc8a34a8a5e93405ae38aa48ea5a28501b5d051c'
step_id: 'S13'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-suite-red-at-head with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-08-13-registry-suite-red-at-head-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Diagnose the absent Modelo 390 page-02 field at official record position 1628 before re-anchoring the disclosure-split gate, per that gate's own instruction and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos/390/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
