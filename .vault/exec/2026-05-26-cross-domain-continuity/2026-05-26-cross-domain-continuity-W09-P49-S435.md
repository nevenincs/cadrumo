---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-17'
step_id: 'S435'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Remove duplicate domain and application public re-exports of the core-owned prorrata-register enums, retain core as the sole facade, and add source-boundary regression coverage.

## Scope

- `src/aeat/core/{_prorrata_register.py`
- `__init__.py} src/aeat/{domain`
- `application}/prorrata_register/ src/aeat/**/tests/`

## Description

- Used RAG and direct facade/core reads to confirm `ProrrataProvisionalProvenance` and `ProrrataRegisterRegime` are closed core-owned axes.
- Removed both enum names from domain and application prorrata-register public exports while retaining private aliases needed for internal typing.
- Added a core-authority regression that combines runtime facade checks with AST source-boundary inspection.
- Ran focused core, domain, application, and duplicate-symbol hygiene coverage with owned Ruff and scoped whitespace checks.

## Outcome

- `aeat.core` is the sole public authority for both prorrata-register enums; neither domain nor application facade republishes them.
- The source regression protects the public-boundary contract without changing application behavior.
- The focused suite passed 52 tests in 24.12 seconds; owned Ruff and whitespace checks passed.

## Notes

- The repair intentionally keeps private aliases inside facades where their internal models and services require the enum types; it removes only duplicate public authority.
