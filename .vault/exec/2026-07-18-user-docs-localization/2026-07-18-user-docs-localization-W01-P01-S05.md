---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S05'
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
     The S05 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Add justfile targets for gettext extraction, a single-language user-scope build, and the full language-matrix build and ## Scope

- `justfile` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add justfile targets for gettext extraction, a single-language user-scope build, and the full language-matrix build

## Scope

- `justfile`

## Description

- Add the `docs-gettext` justfile target (extraction plus catalogue update via `dev.docs.i18n`).
- Add `docs-lang LANG` (single-language user-scope build) and `docs-langs` (the full `es`/`ca`/`hu` matrix), following the existing docs-target style.
- Add a `--language` passthrough to the build driver that sets `CADRUMO_DOCS_LANGUAGE`, forces user scope, and refuses `--scope full` with a language (a localized build is user-scope only). Validation of the tag itself defers to the config, avoiding a second language list.

## Outcome

`just --list` shows the three targets. The scope-conflict guard rejects `--language es --scope full`. A real `docs-lang es` user-scope build completed successfully end to end (build succeeded, HTML written, Pagefind pass), confirming the config wiring resolves the committed catalogue tree.

## Notes

The `--language` build is always user scope because the API autodoc tree stays English by prior ADR.
