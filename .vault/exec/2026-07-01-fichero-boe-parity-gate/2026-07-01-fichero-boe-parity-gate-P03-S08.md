---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S08'
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
     The S08 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Insert a pre-write presence assertion in export_draft that required-applicable casillas are a subset of the on-disk rendered set, raising a hard FilingExportError before write_bytes and ## Scope

- `src/aeat/application/filing/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Insert a pre-write presence assertion in export_draft that required-applicable casillas are a subset of the on-disk rendered set, raising a hard FilingExportError before write_bytes

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Add `assert_export_mirrors_manifest`, called in `export_draft` after the rendered set is known and before `output_path.write_bytes`: for a fixed-width `.boe` whose revision declares a manifest, `missing = (manifest ∩ representable) − rendered` must be empty, else raise a hard `FilingExportError` before any bytes are written.
- Scope the gate to `layout.format == "fixed_width"`; xml_dictionary exports omit absent casillas as absent optional elements (legitimate), so the blank-slot thinness does not apply.

## Outcome

Landed in commit `db7eda99d`. `test_export_completeness_gate.py` proves a thin fixed-width draft panics before writing (no file on disk) and a complete draft exports clean; the sparse M100 xml drafts are not gated. Ruff clean.

## Notes

The fixed-width scoping was found empirically: a first pass false-panicked on M100 (628-casilla xml closure, few declared). Absent xml elements are not thin slots, and the fichero-BOE is by definition the fixed-width DR format, so the scoping aligns with the feature boundary.
