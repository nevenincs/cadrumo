---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S11'
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
     The S11 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Make the panic loud and explicit by enumerating every drifted casilla with expected-versus-actual number, segmento, order and presence in the error and ## Scope

- `src/aeat/application/filing/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Make the panic loud and explicit by enumerating every drifted casilla with expected-versus-actual number, segmento, order and presence in the error

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Make the panic loud and explicit: the `FilingExportError` enumerates every missing casilla with its official record number and segmento (via `_format_missing_casilla`), plus the count and the "structurally-thin filing" label, so the operator sees exactly which required casillas would render blank.

## Outcome

Landed in commit `db7eda99d`. `test_export_completeness_gate.py` asserts the dropped casilla id and the "structurally-thin" phrase appear in the raised error.

## Notes

The number/segmento carried in the message is the structural identity of the drift; it satisfies the intent of the separate numbering/segmento assertion (P03.S09) without a redundant runtime check, since the manifest validator already cross-checks manifest metadata against the registry casilla at registry-build.
