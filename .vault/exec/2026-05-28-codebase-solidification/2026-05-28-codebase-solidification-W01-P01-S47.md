---
step_id: S47
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S47 — ClassificationRuleError introduction

## Outcome

Added `ClassificationRuleError(TransactionError, ValueError)` to
`src/aeat/domain/transactions/_errors.py`. Replaced the bare `raise ValueError(...)`
at line 62 of `src/aeat/domain/transactions/_classification_rule.py` with
`raise ClassificationRuleError(...)`. Added `get_logger` import and module-level
`_logger` to `_classification_rule.py`. Registered
`ERROR_TRANSACTION_CLASSIFICATION_RULE` (`ErrorCategory.ERROR`) in
`src/aeat/core/errors/registry/_domain.py` with
`message_key="errors.error.error_transaction_classification_rule"`. Added the locale
key to en, es, ca, and hu locale files in alphabetical order within the `error:` section.

## Files touched

- `src/aeat/domain/transactions/_errors.py`
- `src/aeat/domain/transactions/_classification_rule.py`
- `src/aeat/core/errors/registry/_domain.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

`uv run --no-sync pytest src/aeat/domain/transactions/test_classification_rule.py -xvs` — 5 passed.
