---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
step_id: 'S446'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W18.P38.S446 - Close AFR-298 for modelo work plazo

Scope: close `AFR-298` for `src/aeat/application/modelo/_work_plazo.py` with signals `active-profile`, `manifest-bucket`, and `plain-file`; target `manifest-discovery`.

## Description

- Audited filing deadline and recargo summary projection for modelo work units.
- Confirmed deadline and recargo logic is delegated to domain deadline services.
- Confirmed the only caught domain deadline failure is logged at debug level before returning a degraded overdue summary.
- Closed `W18.P38.S446` and updated the `AFR-298` register status to `closed`.

## Outcome

`AFR-298` is closed as `manifest-discovery`. The module computes read-only deadline summaries over a supplied work unit and does not own persistence or storage routing.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_work_create_policy.py src/aeat/application/modelo/_work_plazo.py src/aeat/application/modelo/_iva_wallet_seed.py src/aeat/entrypoints/cli/_modelo_projection_cli.py src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py src/aeat/entrypoints/cli/tests/test_modelo_projection.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No source change was required for S446.
