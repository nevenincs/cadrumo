---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
step_id: 'S08'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

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
