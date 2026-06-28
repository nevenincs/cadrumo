---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S108'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-006 for N26 PDF financial provider

## Scope

- `src/aeat/adapters/inbound/financial/providers/_pdf_n26.py`
- `src/aeat/adapters/inbound/financial/providers/test_pdf_n26.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Description

- Classify `PdfN26Provider` as a `plaintext-exception` inbound financial-source parser.
- Replace parser teardown diagnostics that exposed the caller path with the stable `<input-pdf>` placeholder.
- Log the upstream parser exception type without attaching traceback text that can carry raw source paths.
- Raise `InvalidFinancialSourceError` with translated-message metadata for the redacted N26 parse failure.
- Add real-behavior invalid-PDF tests that assert validation warnings and logs omit the source basename and absolute path.
- Remove a tautological assertion from the default-currency enrollment test.
- Repair missing locale catalogue leaves surfaced by `aeat.locales audit` for the N26 parse failure and two existing refused-error keys.

## Outcome

- `uv run ruff check src/aeat/adapters/inbound/financial/providers/_pdf_n26.py src/aeat/adapters/inbound/financial/providers/test_pdf_n26.py` passed.
- `uv run pytest -q src/aeat/adapters/inbound/financial/providers/test_pdf_n26.py src/aeat/test_locale_coverage_inventory.py src/aeat/test_locale_coverage_hardened_errors.py` passed: 219 passed.
- `uv run -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S108` closed the row.

## Notes

- `RawTransaction.provenance.source_path` still carries the resolved source path through the shared financial provider base. This remains a broader secure-storage enrollment follow-up for persisted financial observations.
