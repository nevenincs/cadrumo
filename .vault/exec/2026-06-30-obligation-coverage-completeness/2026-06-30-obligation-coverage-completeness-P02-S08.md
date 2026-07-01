---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S08'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Scaffold the cli.overview.coverage.investigate locale key across the four catalogues once the peer duplicate key clears.

## Scope

- `src/aeat/locales`

## Description

- Scaffold the `cli.overview.coverage.investigate` key from its `tr()` call once the
  peer duplicate `file_idempotent_noop` key cleared, then set the translated value in
  en / es / ca / hu through the locales CLI.

## Outcome

The coverage advisory now renders localized in all four catalogues instead of from its
English `tr(..., default=...)` fallback. Locale parity and translation-honesty gates
pass; `scaffold --check` is clean.

## Notes
