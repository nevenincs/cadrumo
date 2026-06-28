---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S445'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W18.P38.S445 - Close AFR-297 for modelo work create policy

Scope: close `AFR-297` for `src/aeat/application/modelo/_work_create_policy.py` with signals `active-profile` and `plain-file`; target `manifest-discovery`.

## Description

- Audited stub-modelo and applicability gating for modelo work creation.
- Confirmed the M210 live-engine switch reads through centralized `load_settings()`.
- Confirmed active-profile applicability reads remain delegated to workflow/profile services and registry applicability policy.
- Closed `W18.P38.S445` and updated the `AFR-297` register status to `closed`.

## Outcome

`AFR-297` is closed as `manifest-discovery`. The module is a policy facade and does not own secure persistence, manifest scanning, or raw environment handling.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_work_create_policy.py src/aeat/application/modelo/_work_plazo.py src/aeat/application/modelo/_iva_wallet_seed.py src/aeat/entrypoints/cli/_modelo_projection_cli.py src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py src/aeat/entrypoints/cli/tests/test_modelo_projection.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No source change was required for S445.
