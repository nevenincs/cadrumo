---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S110'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-008 for justificante parser dispatch

## Scope

- `src/aeat/adapters/inbound/justificante/_parsers/__init__.py`
- `src/aeat/adapters/inbound/justificante/test_parser.py`

## Description

- Classify the private justificante parser dispatch module as a `plaintext-exception` file-backed parser boundary.
- Convert direct `extract_text()` filesystem read failures into redacted `JustificanteParseError` instances using `<input-pdf>`.
- Preserve structured missing-source metadata, redacted context, and the justificante parse-failure translated-message key.
- Add a real-behavior direct-call test for missing-file redaction through the private dispatch boundary.

## Outcome

- `uv run ruff check src/aeat/adapters/inbound/justificante/_parsers/__init__.py src/aeat/adapters/inbound/justificante/test_parser.py` passed.
- `uv run pytest -q src/aeat/adapters/inbound/justificante/test_parser.py` passed: 79 passed.
- `uv run -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S110` closed the row.

## Notes

- The dispatch cache still keys on the resolved path string for successful parses. This is not emitted directly by the dispatch boundary, but remains adjacent to the broader successful-provenance path follow-up tracked in S109.
