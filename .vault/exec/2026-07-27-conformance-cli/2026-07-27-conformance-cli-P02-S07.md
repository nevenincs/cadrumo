---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S07'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace conformance-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
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
     The extract the fichero-BOE required-applicable casilla derivation into one shared public function consumed by the export gate and ## Scope

- `src/cadrumo/application/filing/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# extract the fichero-BOE required-applicable casilla derivation into one shared public function consumed by the export gate

## Scope

- `src/cadrumo/application/filing/_export.py`

## Description

- Imported `CasillaCollection` from `...domain.filing` in `_export.py`.
- Added `required_applicable_casilla_ids(manifest, *, collection, representable) -> frozenset[CasillaId]` as a public function in `_export.py`, documenting it as the single required-set authority.
- Modified `assert_export_mirrors_manifest` to call `required_applicable_casilla_ids` instead of inlining the set comprehension.
- Added `required_applicable_casilla_ids` to `_export.py`'s `__all__`.
- Added `required_applicable_casilla_ids` to the application `filing` facade import and `__all__`.

## Outcome

`required_applicable_casilla_ids` is the single derivation authority for the required-applicable casilla set. `assert_export_mirrors_manifest` delegates to it. The function is exported through the `application.filing` public facade. Commit: `9c64ec0d99`.

Gates: `ruff check` clean; `pyright` 0 errors; 12 tests in the two filing test modules pass.

## Notes

S07 and S08 land in the same commit (`9c64ec0d99`) because the test re-pointing (S08) depends on the extraction (S07) — they share one atomic pathspec commit per the plan's coupling guidance.
