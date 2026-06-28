---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S370'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S370 - Close AFR-268 for usage-ratio model

Scope: close `AFR-268` for `src/aeat/domain/usage_ratios/_model.py` with signal
`plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited `_model.py` as a pure usage-ratio domain model boundary.
- Confirmed the file has no secure-object, settings, environment, filesystem, or
  database route.
- Confirmed secure-object persistence remains isolated to `_service.py`, which is
  tracked separately.
- Verified typed usage-ratio validation errors and chained enum coercion failures.
- Verified model behavior through focused unit and censo contract tests.
- Closed `W12.P26.S370` through `vaultspec-core vault plan step check` and updated the
  `AFR-268` register status to `closed`.

## Outcome

`AFR-268` is closed. The usage-ratio model file is a justified plaintext exception: it
defines immutable records and pure validation helpers, while persistence remains in the
runtime-default secure-object service.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/usage_ratios/_model.py src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_censo_derivation.py src/aeat/domain/usage_ratios/test_censo_refuse_load.py`
- `uv run --no-sync pytest -q src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_censo_derivation.py src/aeat/domain/usage_ratios/test_censo_refuse_load.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "UsageRatioProfile validate_usage_ratio_reference plaintext exception model only no storage service secure object" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "usage ratios model tests eligible categories MappingProxyType UsageRatioValidationError ratio validation" --type code --port 8766 --max-results 8`

## Notes

No production code change was required. The `src/aeat/domain/transactions/_models.py`
dirty worktree change is unrelated and was left untouched.
