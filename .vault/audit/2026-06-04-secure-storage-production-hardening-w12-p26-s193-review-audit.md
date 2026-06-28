---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S193]]'
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
---

# `secure-storage-production-hardening` `W12.P26.S193` Review

## S193-001 | PASS | Source mesh remains storage-free

`_source_mesh.py` defines source-resolution contracts, merge semantics, and
degradation diagnostics. It does not construct repositories, read settings,
inspect environment variables, or own secure-storage routing. Bucket scope stays
on `CalculationSourceContext.bucket_id` and on concrete resolvers/repositories.

## S193-002 | PASS | Storage degradation is diagnostic and logged

`storage_degradation_resolution` returns an empty resolution with
`storage_degraded` diagnostics and emits a debug log with `exc_info`. It does not
swallow storage failures silently; resolver callers can continue with explicit
degraded-source diagnostics.

## S193-003 | PASS | Source mesh validator errors are localized

`SourceMeshError` now preserves translation keys through both `str(error)` and
`translated_message` for `owned_sources` and `source_transaction_ids` validation
failures. Locale entries were added through `python -m aeat.locales set` for
`ca`, `en`, `es`, and `hu`.

## S193-004 | PASS | Renta source-mesh fixture follows bucket-bound invoice contract

The Renta source-mesh test now injects `InvoiceCatalogueRepository` with
`bucket_id="bucket-a"`, matching the transaction repository and the
`CalculationSourceContext`. This keeps source-mesh coverage aligned with the
S192 fail-closed invoice repository contract.

Validation:

- `uv run --no-sync ruff check src/aeat/application/aggregation/_source_mesh.py src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py src/aeat/application/aggregation/test_source_mesh_profile_live.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py src/aeat/application/aggregation/test_source_mesh_profile_live.py` passed with 19 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Reviewer note: initial S193 review found no critical or high issues and raised
one low localization concern for raw `SourceMeshError` validator messages. That
low concern was fixed before closure and sent through re-review.

Disposition: close `AFR-091`.
