---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S113'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-011 for sanitizer errors

## Scope

- `src/aeat/adapters/inbound/sanitizer/_errors.py`
- `src/aeat/adapters/inbound/sanitizer/test_errors.py`

## Description

- Classify the sanitizer error module as a `remote-mirror`-adjacent error boundary.
- Add a redacted `SanitizerSourceParseError` constructor with `<input-pdf>` context, parser-failure type metadata, and the existing source-parse translated-message key.
- Preserve positional-message compatibility while refusing to render or context-copy legacy raw parser diagnostics.
- Remove the stale contract that encouraged raw pikepdf/QPDF exception chaining from sanitizer source-parse errors.
- Stop rendering the full source PDF digest in `AlreadySanitizedError` while preserving it as a typed attribute for internal callers.
- Add real error-contract tests for hierarchy, redacted messages, structured context, translated-message keys, and full-digest non-rendering.

## Outcome

- `uv run ruff check src/aeat/adapters/inbound/sanitizer/_errors.py src/aeat/adapters/inbound/sanitizer/test_errors.py` passed.
- `uv run pytest -q src/aeat/adapters/inbound/sanitizer/test_errors.py src/aeat/adapters/inbound/sanitizer/test_pipeline.py` passed: 8 passed.
- `uv run -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S113` closed the row.

## Notes

- S113 hardens the sanitizer error classes and their direct contract. The runtime pikepdf call site in `src/aeat/adapters/inbound/sanitizer/_pipeline.py` still needs the immediately following S114 migration so it stops interpolating raw upstream exception text and stops logging raw tracebacks.
