---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-06'
modified: '2026-06-06'
step_id: 'S455'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W20.P41.S455 inbound provenance privacy

Scope: execute `W20.P41.S455` from the secure-storage production hardening plan.

## Description

- Add a shared digest-derived PDF source reference for parser provenance records.
- Normalize declaración, justificante, and borrador `source_pdf_path` outputs away from local filesystem paths.
- Replace the justificante text-dispatch cache key with a bounded digest-keyed cache.
- Redact the borrador artefact-detection error source label.
- Pin real-behavior parser tests for persisted provenance and cache-key path privacy.

## Outcome

S455 closes the open provenance-path findings for parsed PDF records and the successful justificante dispatch cache. Successful parser records now persist `.secure-source/<sha256>.pdf` references instead of source filenames or resolved paths, while extraction still reads the real file when needed.

Focused validation passed:

- `uv run --no-sync pytest src/aeat/adapters/inbound/pdf/tests/test_utils.py src/aeat/adapters/inbound/justificante/tests/test_parser.py src/aeat/adapters/inbound/borrador/tests/test_modelo_100_summary.py -q`
- `uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary.py::test_parser_extracts_legal_entity_nif_from_pdf -q`
- `uv run --no-sync ruff check ...` across the edited inbound parser, schema, and test files.

## Notes

The full declaration parser boundary module is corpus-heavy and timed out when batched with all other focused modules. The targeted declaration provenance test was run separately and passed.

Sanitizer `real_sha256` rows remain documented as contributor-local sanitization audit metadata, not runtime secure-storage state. No production persistence path for those rows was changed in this step.
