---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:006ba15505cca095d681cdae873c571b698fa054540394d133194f78e3e0b0e3'
step_id: 'S88'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Add safe per-locale selection to product-identity canonicalization

## Scope

- `src/cadrumo locale manager`
- `CLI`
- `and cohesive tests`

## Description

- Add an optional `--locale` selector bound to the canonical `OutputLanguage`
  enumeration.
- Resolve selected catalogues through the manager's contained locale-path
  validation while preserving all-catalogue behavior when omitted.
- Exercise real Typer parsing and command dispatch against actual temporary
  catalogue files through a typed Click context seam.
- Prove selected, invalid, and omitted-selector behavior without touching the
  workspace catalogues.

## Outcome

`canonicalize-product-identity --locale en` now targets exactly the English
catalogue. The accepted values are derived from `OutputLanguage` and render as
`[es|en|ca|hu]`; traversal-shaped and arbitrary values fail during production
CLI parsing before manager mutation. The selected file is still resolved by
the manager's existing containment and existence checks. Omitting `--locale`
retains the original behavior of scanning every catalogue.

Real CLI tests used a real `LocaleManager` rooted at temporary YAML catalogues.
They proved that English-only execution changed one file and preserved the
other three byte-for-byte, invalid selection changed none, and omitted selection
changed all four. Thirty-seven focused locale and renderer tests, scoped Ruff, and scoped Ty
passed. Live command help exposed the four production-supported locale choices,
and a real invalid traversal probe was refused.

## Notes

No workspace locale YAML was modified. The context object is used only when it
contains an actual `LocaleManager`; normal operator execution continues to build
the production manager. The shared test runner's typed invocation surface now
records Click's existing `obj` argument so the real-manager seam is statically
honest rather than passed as an undeclared keyword.
