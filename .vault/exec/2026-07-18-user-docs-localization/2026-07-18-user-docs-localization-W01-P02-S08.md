---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S08'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace user-docs-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Extend the build gate with per-language nitpicky warnings-as-errors user-scope builds for es, ca, and hu and ## Scope

- `dev/docs/tests/test_docs_build.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extend the build gate with per-language nitpicky warnings-as-errors user-scope builds for es, ca, and hu

## Scope

- `dev/docs/tests/test_docs_build.py`

## Description

- Extend the build gate with a parametrized per-language nitpicky warnings-as-errors user-scope build for `es`, `ca`, and `hu`, reusing the existing user-scope build harness with `CADRUMO_DOCS_LANGUAGE` set.
- Source the language parameters from the shared `TARGET_LANGUAGES` so no second language list appears.

## Outcome

GREEN. All three languages build clean under `-n -W` (3 passed in 16m32s). Untranslated segments fall back to English at render time, so the structural build is as clean in every language as in English; the completeness gate, not this build, refuses the fallback.

## Notes

The matrix is the localized user-scope build the ADR anticipated the docs CI would grow. Runtime is dominated by the per-language user-scope autodoc-free build; it runs in the docs-check lane, not the fast unit lane.
