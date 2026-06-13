---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S105'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-003 for Borrador pdfplumber backend

## Scope

- `src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py`
- `src/aeat/adapters/inbound/pdf/_pdfplumber.py`
- `src/aeat/adapters/inbound/pdf/test_pdfplumber.py`

## Description

- Classify the Borrador pdfplumber backend as a `plaintext-exception` inbound parser boundary.
- Confirm the backend delegates PDF text extraction to the shared pdfplumber primitive and does not persist files, construct repositories, or manage secure-storage state.
- Cross-close the intersecting shared primitive row because the privacy issue discovered during S105 lived in `src/aeat/adapters/inbound/pdf/_pdfplumber.py`.

## Outcome

- `uv run --no-sync ruff check src/aeat/adapters/inbound/pdf/_pdfplumber.py src/aeat/adapters/inbound/pdf/test_pdfplumber.py src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py` passed.
- `uv run pytest -q src/aeat/adapters/inbound/pdf/test_pdfplumber.py src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py` passed: 20 passed.
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md S105` closed the row.

## Notes

- The backend itself required no direct code change. The shared pdfplumber primitive now redacts path-based failure diagnostics to `<input-pdf>`.
