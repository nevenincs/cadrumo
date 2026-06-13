---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S106'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-004 for Declaracion parser entry point

## Scope

- `src/aeat/adapters/inbound/declaracion/_parser.py`
- `src/aeat/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py`
- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`
- `src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py`
- `src/aeat/adapters/inbound/declaracion/test_pdfplumber_backend_privacy.py`

## Description

- Classify `parse_declaracion` and `parse_declaracion_bytes` as `plaintext-exception` inbound parser boundaries.
- Confirm the parser returns typed `DeclaracionObservation` data and does not persist secure objects, construct repositories, or derive secure-storage namespaces.
- Replace source-path debug logging with the stable `source=<input-pdf>` placeholder.
- Replace template-not-detected path context with `<input-pdf>` so locale-rendered error messages do not expose operator filenames.
- Replace word-position fallback logging of raw paths with `<input-pdf>` plus the upstream exception type.
- Replace pypdfium fast-path fallback logging of raw paths with `<input-pdf>` plus the upstream exception type.
- Add real-behavior tests for successful parser logging, template-not-detected error context, and word-extraction fallback logging.
- Add a backend fallback privacy test for the pypdfium debug log.

## Outcome

- `uv run --no-sync ruff check src/aeat/adapters/inbound/declaracion/_parser.py src/aeat/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py src/aeat/adapters/inbound/declaracion/test_pdfplumber_backend_privacy.py` passed.
- `uv run pytest -q src/aeat/adapters/inbound/declaracion/test_parser_boundary.py::test_parser_debug_log_does_not_expose_source_filename src/aeat/adapters/inbound/declaracion/test_parser_boundary.py::test_template_not_detected_context_does_not_expose_source_filename src/aeat/adapters/inbound/declaracion/test_parser_boundary.py::test_word_extraction_debug_log_does_not_expose_source_filename src/aeat/adapters/inbound/declaracion/test_pdfplumber_backend_privacy.py src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py` passed: 9 passed.
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md S106` closed the row.

## Notes

- A full run of `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py` timed out in this environment after roughly three minutes. The committed gate uses the three new targeted tests plus the exception-hygiene scanner.
