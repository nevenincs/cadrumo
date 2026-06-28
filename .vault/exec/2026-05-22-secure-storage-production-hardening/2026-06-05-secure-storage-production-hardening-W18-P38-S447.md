---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S447'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W18.P38.S447 - Close AFR-299 for IVA wallet seed facade

Scope: close `AFR-299` for `src/aeat/application/modelo/_iva_wallet_seed.py` with signals `active-profile`, `manifest-bucket`, and `plain-file`; target `manifest-discovery`.

## Description

- Audited bucket-scoped IVA compensation seed facade.
- Confirmed taxpayer identity lookup delegates to the IVA wallet gate and persistence delegates to the calculation seed service.
- Confirmed seed refusals derive from `ModeloError`/`AeatError` and use translated message keys.
- Closed `W18.P38.S447` and updated the `AFR-299` register status to `closed`.

## Outcome

`AFR-299` is closed as `manifest-discovery`. The module validates seed amount and delegates runtime custody; it does not construct repositories or bypass encrypted storage APIs.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_work_create_policy.py src/aeat/application/modelo/_work_plazo.py src/aeat/application/modelo/_iva_wallet_seed.py src/aeat/entrypoints/cli/_modelo_projection_cli.py src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py src/aeat/entrypoints/cli/tests/test_modelo_projection.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No source change was required for S447.
