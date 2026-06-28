---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S449'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W18.P38.S449 - Close AFR-301 for modelo IVA wallet CLI

Scope: close `AFR-301` for `src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py` with signals `active-profile`, `manifest-bucket`, and `plain-file`; target `manifest-discovery`.

## Description

- Audited IVA wallet balance and seed CLI registration after module split.
- Confirmed balance reads and seed writes delegate to application services instead of CLI-owned storage code.
- Confirmed seed parsing/refusals use localized Typer errors and registered application errors.
- Closed `W18.P38.S449` and updated the `AFR-301` register status to `closed`.

## Outcome

`AFR-301` is closed as `manifest-discovery`. The CLI registrar remains a thin localized command surface over runtime-managed IVA wallet services.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_work_create_policy.py src/aeat/application/modelo/_work_plazo.py src/aeat/application/modelo/_iva_wallet_seed.py src/aeat/entrypoints/cli/_modelo_projection_cli.py src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py src/aeat/entrypoints/cli/tests/test_modelo_projection.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No source change was required for S449.
