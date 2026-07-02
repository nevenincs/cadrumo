---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S12'
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
     The S12 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Emit a non-blocking loud coverage advisory Notice when the completeness manifest is absent or manual_extraction and ## Scope

- `src/aeat/application/filing/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit a non-blocking loud coverage advisory Notice when the completeness manifest is absent or manual_extraction

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Compute `completeness_unverified` in `export_modelo_revision` from the export subview (`fixed_width` layout format AND absent completeness manifest), add the field plus a `completeness_advisory_message` property to `ModeloExportResult`.

## Outcome

Landed in commit `d4810b27a`. Implemented at the modelo layer (not `_export.py`, which carried active peer WIP), so the gate's manifest-absent case surfaces a signal rather than implying the export was verified.

## Notes

The advisory rides the typed `Notice` channel, not the result payload, per `cli-notices-are-the-only-diagnostic-channel`.
