---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S03'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Assert BindingPreviewRowPayload (A2) and _BindingRow (A4) are already role-distinct / module-private at HEAD and confirm no bare BindingRow stem collision remains and ## Scope

- `rename _BindingRow to _EntradasBindingRow only if a residual stem collision is found in calc_sheets/_layout.py`
- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/application/storage/calc_sheets/_layout.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Assert BindingPreviewRowPayload (A2) and _BindingRow (A4) are already role-distinct / module-private at HEAD and confirm no bare BindingRow stem collision remains

## Scope

- `rename _BindingRow to _EntradasBindingRow only if a residual stem collision is found in calc_sheets/_layout.py`
- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/application/storage/calc_sheets/_layout.py`

## Description

- Assert `BindingPreviewRowPayload` (A2) is already role-distinct at HEAD: it carries its own name with no bare `BindingRow` stem and exists at the def in `_modelo_payloads.py`.
- Assert `_BindingRow` (A4) is module-private to `calc_sheets/_layout.py`: all six occurrences (def plus five uses) are confined to that one file with zero cross-module reach.
- Confirm the bare `BindingRow` stem search across `src/` returns no matches after S01 and S02 landed, so no residual stem collision remains.

## Outcome

No-op assert Step, no code change and no commit. A2 and A4 are confirmed genuine no-ops. The optional `_BindingRow` to `_EntradasBindingRow` rename was conditioned on finding a residual stem collision; none exists (the module-private symbol cannot collide outside its file, and the bare-stem grep is empty), so the rename was correctly skipped.

## Notes

None.
