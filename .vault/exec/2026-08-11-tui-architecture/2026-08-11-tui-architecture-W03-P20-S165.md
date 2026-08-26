---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:36f61de702d0a276e3f60f3be5ab3d168e16beab7f9863ad8e78d31d3302458d'
step_id: 'S165'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Define the canonical locale-catalogue native atomic capture, owner generation, and neutral opaque comparison domain in the sole public locales/locale_catalogue.py defining module, migrate every exact consumer to direct defining-module imports, and delegate to the existing canonical key resolution, Spanish fallback, suppression, catalogue loading, and digest semantics without reimplementation, package re-export, alias, shim, fallback, or bridge

## Scope

- `src/cadrumo/locales/locale_catalogue.py`
- `every affected production/test/annotation/registration/dynamic/tooling consumer`
- `and focused locale parity/currentness/direct-import/sole-authority tests`

## Changes

- `A` `src/cadrumo/core/i18n/locale_catalogue.py`
- `A` `src/cadrumo/core/i18n/tests/test_locale_catalogue_capture.py`
- `M` `src/cadrumo/core/errors/registry/_core.py`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `M` `docs/api/cadrumo.core.i18n.rst`
- `A` `docs/api/cadrumo.core.i18n.locale_catalogue.rst`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/core/i18n/tests/test_locale_catalogue_capture.py -n0` -> `pass`

## Notes

The Step row names `locales/locale_catalogue.py`. That directory ships
catalogue data only and is a namespace package by design, stated in the
existing catalogue reader, so the capture lives with the catalogue's runtime
owner in `core/i18n/`. The Step also asks for delegation to the Spanish
fallback; that resolver is domain-layer and core cannot import it without
inverting the layering, so the capture covers the catalogue substrate the
resolver reads and does not reimplement the fallback.
