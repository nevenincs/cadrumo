---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S278-001 | PASS | Structured context redaction

The review found that wizard widget validators previously passed rejected raw answers
through `WizardValidationError.context`. The repair keeps a separate render context
for `tr(...)` and stores a redacted context on the exception. `raw` is replaced with
`raw_redacted` and `raw_length`; identity-validator `detail` is replaced with
`detail_redacted`.

## S278-002 | PASS | Exception and localization contract

The validators still raise `WizardValidationError`, which derives from the AEAT core
exception hierarchy. Operator-facing messages continue to flow through locale keys
such as `wizard.errors.invalid_tax_id`, `wizard.errors.invalid_confirm`, and related
widget errors.

## S278-003 | PASS | Tests and locale gate

The added tests exercise the production validator entry point and production exception
type. They do not mock, monkeypatch, skip, xfail, or duplicate widget validation logic.
The locale repair used `python -m aeat.locales` and the canonical audit reports all
four catalogues clean.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/wizard/_widgets.py src/aeat/application/wizard/test_widgets.py src/aeat/application/wizard/_errors.py`
- `uv run --no-sync pytest -q src/aeat/application/wizard/test_widgets.py src/aeat/application/wizard/test_setup_compiles.py src/aeat/test_locale_coverage_hardened_errors.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "wizard widgets validation localized errors no storage plaintext exception" --type code --port 8766 --max-results 8`

Disposition: close `AFR-176`.
