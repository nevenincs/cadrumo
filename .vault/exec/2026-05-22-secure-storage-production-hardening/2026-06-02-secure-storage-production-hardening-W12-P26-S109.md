---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S109'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-007 for justificante parser entry point

## Scope

- `src/aeat/adapters/inbound/justificante/_parser.py`
- `src/aeat/domain/justificante/_errors.py`
- `src/aeat/adapters/inbound/justificante/test_parser.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Description

- Classify `parse_justificante` as a `plaintext-exception` inbound PDF parser boundary.
- Replace missing-file and debug-log source diagnostics with the stable `<input-pdf>` placeholder.
- Wrap path-bearing extractor failures at the parser boundary while preserving `JustificanteParseError` subclasses and structured extraction attributes.
- Extend `JustificanteParseError` to carry `context`, `suggestion`, and `translated_message` metadata like the declaración parse-error boundary.
- Add real-behavior tests for missing-file redaction, debug-log redaction, and non-justificante PDF parse-error redaction.
- Enroll the new justificante parse-failure locale key via `python -m aeat.locales`.

## Outcome

- `uv run ruff check src/aeat/adapters/inbound/justificante/_parser.py src/aeat/adapters/inbound/justificante/test_parser.py src/aeat/domain/justificante/_errors.py` passed.
- `uv run pytest -q src/aeat/adapters/inbound/justificante/test_parser.py src/aeat/test_locale_coverage_inventory.py src/aeat/test_locale_coverage_hardened_errors.py` passed: 286 passed.
- `uv run -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S109` closed the row.

## Notes

- `Justificante.source_pdf_path` still carries the resolved source path as provenance for successfully parsed records. This remains a broader secure-storage enrollment decision for persisted filing artifacts.
