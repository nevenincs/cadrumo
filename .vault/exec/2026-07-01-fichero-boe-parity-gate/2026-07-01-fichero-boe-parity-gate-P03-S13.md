---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S13'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace fichero-boe-parity-gate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Surface the coverage advisory and propagate the hard parity error on the export_modelo_revision envelope and ## Scope

- `src/aeat/application/modelo/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Surface the coverage advisory and propagate the hard parity error on the export_modelo_revision envelope

## Scope

- `src/aeat/application/modelo/_export.py`

## Description

- Emit the coverage advisory on the `modelo export` CLI envelope: add `_completeness_advisory_notice` (WARNING severity, code `modelo.export.completeness_unverified`) and `_export_notices`, which appends it when `result.completeness_unverified`.

## Outcome

Landed in commit `d4810b27a`. Verified by `test_export_completeness_advisory.py` (2 tests): an unverified export emits the advisory notice; a verified/non-fichero-BOE export does not.

## Notes

The hard parity error already propagates naturally as a `FilingExportError` raised inside `export_draft` (before the CLI builds its envelope), so no extra propagation wiring was needed for the panic path.
