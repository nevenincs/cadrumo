---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S342'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S342 - Close AFR-240 for invoice models

Scope: close `AFR-240` for `src/aeat/domain/invoices/_models.py` with signal
`manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`.

## Description

- Audited invoice models against the runtime-storage rollout register and adjacent
  invoice repository.
- Used vaultspec RAG to compare the invoice model and secure-object repository split
  against semantically similar catalogue and manifest surfaces.
- Reviewed export taxonomy, two-way sync, calc-sheets parity, and secure-storage
  export-exception ADRs for boundary conflicts.
- Wrapped invoice date parser and enum conversion failures in `InvoiceValidationError`.
- Added model-boundary tests for invalid `issued_at` and invalid invoice kind payloads.
- Closed `W12.P26.S342` through `vaultspec-core vault plan step check` and updated the
  `AFR-240` register status to `closed`.

## Outcome

`AFR-240` is closed. `src/aeat/domain/invoices/_models.py` remains a strict frozen
manifest-discovery model surface with no storage-route authority. Validation hardening
keeps malformed invoice payloads inside the invoice-domain error hierarchy before
pydantic wraps them for callers.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/invoices/_models.py src/aeat/domain/invoices/test_models.py src/aeat/domain/invoices/test_repository.py src/aeat/domain/invoices/_repository.py`
- `uv run --no-sync pytest -q src/aeat/domain/invoices/test_models.py src/aeat/domain/invoices/test_repository.py`
- `uv run --no-sync pytest -q src/aeat/domain/invoices/test_models.py src/aeat/domain/invoices/test_repository.py src/aeat/application/invoices/test_linking.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `uv run --no-sync ruff check src/aeat/domain/invoices/_models.py src/aeat/domain/invoices/_errors.py src/aeat/domain/invoices/_repository.py src/aeat/domain/invoices/test_models.py src/aeat/domain/invoices/test_repository.py src/aeat/application/invoices/test_linking.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

S343 remains open for `src/aeat/domain/invoices/_repository.py`, the actual
runtime-default secure-object repository edge. This step deliberately did not touch
S298, because a parallel agent owns that edge.
