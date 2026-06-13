---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S370]]'
---

# `secure-storage-production-hardening` `W12.P26.S370` Review

## S370-001 | PASS | Usage-ratio model file is a plaintext exception, not storage

`_model.py` defines strict frozen Pydantic records and pure helpers for usage-ratio
validation. It does not construct secure-object repositories, load settings, read
environment variables, or perform file/database I/O. The secure-object persistence route
lives in `_service.py`, which is tracked separately as a runtime-default row.

## S370-002 | PASS | Validation failures are typed domain errors

`UsageRatioProfile` and `validate_usage_ratio_reference` raise
`UsageRatioValidationError` for invalid ratios, category mismatch, unknown references,
and persisted-business-percentage drift. External enum coercion failures are wrapped
with chained `ValueError` causes where applicable.

## S370-003 | PASS | Model behavior is covered by focused tests

The model tests cover ratio bounds, finite-number rejection, eligible-category gating,
immutable mapping behavior, deterministic serialization order, with/without ratio
derivations, and ledger-reference validation. Censo derivation/refusal tests cover the
model's interaction with the censo-derived usage-ratio contract.

## S370-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/usage_ratios/_model.py src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_censo_derivation.py src/aeat/domain/usage_ratios/test_censo_refuse_load.py` passed.
- `uv run --no-sync pytest -q src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_censo_derivation.py src/aeat/domain/usage_ratios/test_censo_refuse_load.py` passed with 34 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-rag search "UsageRatioProfile validate_usage_ratio_reference plaintext exception model only no storage service secure object" --type code --port 8766 --max-results 8` returned the model and separate service storage boundary.
- `uv run --no-sync vaultspec-rag search "usage ratios model tests eligible categories MappingProxyType UsageRatioValidationError ratio validation" --type code --port 8766 --max-results 8` returned the model validation and test evidence.

Reviewer note: no critical, high, medium, or low plaintext-exception findings remain
for the S370 slice.

Disposition: close `AFR-268` as `plaintext-exception`.
