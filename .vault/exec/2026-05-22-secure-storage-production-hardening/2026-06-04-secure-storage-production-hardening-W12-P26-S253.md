---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S253'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s253-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S253`

Closed `AFR-151` for setup command/result contracts.

## Description

- Reviewed `src/aeat/application/setup/_contracts.py` as a manifest-discovery contract surface.
- Verified the contracts use shared `ProfileId`, `BucketId`, `OutputLanguage`, and `IVARegime` types rather than duplicate local enums.
- Verified the contract module does not read or write storage, resolve active profiles, or expose a CLI command surface.
- Verified focused setup contract and provisioning tests still pass.
- Closed `S253` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-151` is closed as `manifest-discovery`. The setup contract module remains a strict typed DTO boundary for the atomic setup service; secure storage behavior is owned by the setup service and bucket/profile orchestration, not by the contract definitions.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/setup/_contracts.py src/aeat/application/setup/test_contracts_output_language_roundtrip.py src/aeat/application/setup/test_service_provisions_bucket.py`
- `uv run --no-sync pytest -q src/aeat/application/setup/test_contracts_output_language_roundtrip.py src/aeat/application/setup/test_service_provisions_bucket.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No code change was required for S253. The deprecated CLI init concern belongs to command routing and setup service enrollment, not this Pydantic contract module.
