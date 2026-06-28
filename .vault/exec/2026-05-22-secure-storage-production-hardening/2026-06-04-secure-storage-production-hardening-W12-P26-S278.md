---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S278'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S278 - Close AFR-176 for wizard widgets

Scope: close `AFR-176` for `src/aeat/application/wizard/_widgets.py` with signals
`plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Split widget-validation render context from stored exception context.
- Redacted raw operator answers and identity diagnostics from `WizardValidationError`
  structured context while preserving existing localized operator messages.
- Added real validator tests that assert rejected confirm and tax-id answers do not
  leave `raw` or identity `detail` fields in `error.context`.
- Repaired concurrent locale drift through the canonical `python -m aeat.locales`
  set/remove/audit workflow.

## Outcome

`AFR-176` is closed as `plaintext-exception`. Widget validation errors remain typed
AEAT exceptions with localized messages, but logs and JSON envelopes no longer receive
raw rejected answers through structured context.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/wizard/_widgets.py src/aeat/application/wizard/test_widgets.py src/aeat/application/wizard/_errors.py`
- `uv run --no-sync pytest -q src/aeat/application/wizard/test_widgets.py src/aeat/application/wizard/test_setup_compiles.py src/aeat/test_locale_coverage_hardened_errors.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "wizard widgets validation localized errors no storage plaintext exception" --type code --port 8766 --max-results 8`

## Notes

The localized rendered message still follows the existing wizard error contract. This
step specifically hardens structured diagnostic context used by logs and envelopes.
