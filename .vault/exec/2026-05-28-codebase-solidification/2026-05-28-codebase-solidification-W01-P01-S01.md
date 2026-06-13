---
step_id: S01
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S01 — TaxationComparisonError base rebind

## Outcome

Replaced `class TaxationComparisonError(Exception)` with
`class TaxationComparisonError(CoreError)` at line 220 of
`src/aeat/application/modelo/_taxation_comparison.py`. Added
`from ...core.errors import CoreError` import.

Registered `REFUSED_TAXATION_COMPARISON` (`ErrorCategory.REFUSED`) in
`src/aeat/core/errors/registry/_application.py` with
`message_key="errors.refused.refused_taxation_comparison"`. Added the
locale message key to all four locale files (en, es, ca, hu) in
alphabetical order within the `refused:` section.

## Files touched

- `src/aeat/application/modelo/_taxation_comparison.py`
- `src/aeat/core/errors/registry/_application.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

`vault plan step check W01.P01.S01` applied after commit.
