---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace export-publication with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Re-export the typed profile export service as the sole public export orchestration API and ## Scope

- `src/cadrumo/application/user_profile/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-export the typed profile export service as the sole public export orchestration API

## Scope

- `src/cadrumo/application/user_profile/__init__.py`

## Description

- Extend the `user_profile` package facade in `__init__.py` to re-export the full typed export service as the sole public orchestration API.
- Add `PreparedProfileExport`, `ProfileBundleExportTarget`, `bundle_data_categories`, `prepare_profile_export`, `publish_prepared_export`, and `reconcile_prepared_exports` to the `TYPE_CHECKING` import block, the lazy `__getattr__` dispatch, and `__all__`, keeping `__all__` sorted for the ruff gate.

## Outcome

Cross-package consumers reach every export symbol through the package top-level facade; no consumer needs to dot into a private `_bundle_export*` submodule. Committed in `a9251f5fa2`.

## Notes

None.
