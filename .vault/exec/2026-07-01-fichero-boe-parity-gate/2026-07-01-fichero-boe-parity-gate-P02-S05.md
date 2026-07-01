---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S05'
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
     The S05 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Add a helper for the manifest required set restricted to casillas representable in an applicable non-suppressed record, carrying number, segmento and record-order metadata and ## Scope

- `src/aeat/application/filing/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a helper for the manifest required set restricted to casillas representable in an applicable non-suppressed record, carrying number, segmento and record-order metadata

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Make `boe_representable_casilla_ids` disposition-aware by skipping records suppressed for the draft's disposition (`_did_page_suppressed`, e.g. the DID refund page on a non-refund filing), so the applicable-required set the gate computes as `manifest ∩ representable` excludes casillas that legitimately do not render for this filing.

## Outcome

Landed with S04/S06/S07 in the P02 commit. The applicable restriction is carried by the representable helper's suppression pass rather than a separate function.

## Notes

The manifest carries `number`/`segmento` metadata per casilla for the P03 structural-fidelity assertion; record-order metadata comes from the layout's `ExportRecordDefinition.order`.
