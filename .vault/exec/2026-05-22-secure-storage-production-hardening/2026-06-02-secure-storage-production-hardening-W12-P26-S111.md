---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S111'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-009 for shared pdfplumber primitive

## Scope

- `src/aeat/adapters/inbound/pdf/_pdfplumber.py`
- `src/aeat/adapters/inbound/pdf/test_pdfplumber.py`

## Description

- Classify the shared pdfplumber primitive as a `plaintext-exception` inbound parser utility.
- Replace path-bearing parser failure messages with the stable `<input-pdf>` source placeholder for missing, invalid, and scan-only path inputs.
- Replace upstream pdfplumber exception interpolation with the upstream exception type name so third-party exception text cannot reintroduce operator file paths.
- Add real-behavior tests for missing files, invalid PDF files, blank PDFs, and concatenated extraction failures.

## Outcome

- `uv run --no-sync ruff check src/aeat/adapters/inbound/pdf/_pdfplumber.py src/aeat/adapters/inbound/pdf/test_pdfplumber.py src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py` passed.
- `uv run pytest -q src/aeat/adapters/inbound/pdf/test_pdfplumber.py src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py` passed: 20 passed.
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md S111` closed the row.

## Notes

- Byte-stream extraction keeps caller-provided `source_label` behavior unchanged in this step; the hardened surface here is filesystem path input.
