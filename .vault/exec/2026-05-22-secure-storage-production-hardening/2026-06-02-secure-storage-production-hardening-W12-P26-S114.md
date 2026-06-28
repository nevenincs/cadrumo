---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S114'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-012 for sanitizer pipeline

## Scope

- `src/aeat/adapters/inbound/sanitizer/_pipeline.py`
- `src/aeat/adapters/inbound/sanitizer/test_pipeline.py`

## Description

- Classify the sanitizer pipeline as a `remote-mirror` pipeline with file-backed PDF input handling.
- Convert missing-path digest failures into redacted `SanitizerSourceParseError` instances without raw cause or context retention.
- Convert pikepdf parse failures into redacted `SanitizerSourceParseError` instances without raw parser text, cause chaining, or context retention.
- Replace raw traceback/error logging on parse failure with a redacted debug diagnostic carrying only `<input-pdf>` and the exception type.
- Add real pipeline tests for missing path and invalid PDF bytes that assert message, structured context, debug log, `__cause__`, and `__context__` redaction.

## Outcome

- `uv run ruff check src/aeat/adapters/inbound/sanitizer/_pipeline.py src/aeat/adapters/inbound/sanitizer/test_pipeline.py` passed.
- `uv run pytest -q src/aeat/adapters/inbound/sanitizer/test_pipeline.py` passed: 8 passed.
- `uv run pytest -q src/aeat/adapters/inbound/sanitizer/test_errors.py src/aeat/adapters/inbound/sanitizer/test_pipeline.py` passed: 10 passed.
- `uv run -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S114` closed the row.

## Notes

- The S113 follow-up for the sanitizer runtime call site is now closed. The remaining sanitizer pipeline info log still reports short SHA prefixes for successful sanitization output provenance; this step targeted failure emission and raw upstream diagnostics.
