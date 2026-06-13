---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S112'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-010 for shared PDF hash utility

## Scope

- `src/aeat/adapters/inbound/pdf/_utils.py`
- `src/aeat/adapters/inbound/pdf/test_utils.py`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/hu.yml`

## Description

- Classify the shared PDF hashing utility as a `plaintext-exception` file-backed boundary.
- Convert `sha256_file()` filesystem read failures into `PdfModeloImportError` with `<input-pdf>` as the rendered source label.
- Emit a redacted debug diagnostic for the filesystem failure type and suppress the raw exception cause chain so traceback-oriented diagnostics do not retain the operator path.
- Add the `adapters.inbound.pdf.errors.hash_failed` translated-message key through `python -m aeat.locales`.
- Add real-behavior tests for successful digest calculation and missing-file redaction.

## Outcome

- `uv run ruff check src/aeat/adapters/inbound/pdf/_utils.py src/aeat/adapters/inbound/pdf/test_utils.py` passed.
- `uv run pytest -q src/aeat/adapters/inbound/pdf/test_utils.py` passed: 2 passed.
- `uv run -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run pytest -q src/aeat/test_locale_coverage_inventory.py src/aeat/test_locale_coverage_hardened_errors.py` passed: 208 passed.
- `uv run vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S112` closed the row.

## Notes

- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` still reports only the plan-level `PLAN022` canonical-id monotonicity warning. S112 itself is closed and the AFR register is synchronized.
- Successful `sha256_file()` calls still read and hash the caller-supplied file path because the digest helper necessarily operates on an on-disk artefact; this step only changes failure emission.
