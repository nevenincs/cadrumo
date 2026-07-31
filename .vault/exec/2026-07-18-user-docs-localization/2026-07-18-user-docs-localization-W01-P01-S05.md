---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:903dcc65f016eb14c2dbec0688666887ba0bab1de8a08d12d31fd76503b1fb2d'
step_id: 'S05'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

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
