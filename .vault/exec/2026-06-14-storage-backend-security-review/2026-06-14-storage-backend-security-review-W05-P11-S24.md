---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S24'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S24 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Rebind the private bucket-submodule imports in profile health and overview to the bucket package surface and ## Scope

- `src/aeat/application/workflow/_profile_health.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rebind the private bucket-submodule imports in profile health and overview to the bucket package surface

## Scope

- `src/aeat/application/workflow/_profile_health.py`

## Description

- Rebind `_profile_health` (5 symbols) and `_overview` (1 symbol) from the private
  `bucket._layout` / `._manifest` / `._manifest_io` submodules to the `bucket`
  package surface.

## Outcome

Private-submodule imports replaced with package-surface imports; all symbols are
in `bucket.__all__`. 146 affected-suite tests green; storage smoke (every `__all__`
name importable) green. Committed in `c22f87dbc`.

## Notes

None.
