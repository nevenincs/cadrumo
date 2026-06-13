---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S448'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W18.P38.S448 - Close AFR-300 for modelo projection CLI

Scope: close `AFR-300` for `src/aeat/entrypoints/cli/_modelo_projection_cli.py` with signals `active-profile` and `plain-file`; target `manifest-discovery`.

## Description

- Audited projection and comparison CLI registration after module split.
- Confirmed command output uses registered Pydantic payloads and `_emit_envelope()`.
- Confirmed typed projection exceptions are localized through shared BadParameter renderers and unexpected exceptions remain for the command boundary.
- Closed `W18.P38.S448` and updated the `AFR-300` register status to `closed`.

## Outcome

`AFR-300` is closed as `manifest-discovery`. The CLI registrar delegates runtime reads to application services and does not own secure storage routing.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_work_create_policy.py src/aeat/application/modelo/_work_plazo.py src/aeat/application/modelo/_iva_wallet_seed.py src/aeat/entrypoints/cli/_modelo_projection_cli.py src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py src/aeat/entrypoints/cli/tests/test_modelo_projection.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_projection.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No source change was required for S448.
