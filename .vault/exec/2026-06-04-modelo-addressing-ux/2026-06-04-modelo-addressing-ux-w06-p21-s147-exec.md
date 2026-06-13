---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S147'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P21.S147 Exact CLI boundary closure audit

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/_modelo_cli_support.py`
- `src/aeat/entrypoints/cli/_modelo_export_cli.py`
- `src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py`
- `src/aeat/entrypoints/cli/_modelo_m036_cli.py`
- `src/aeat/entrypoints/cli/_modelo_maritime_cli.py`
- `src/aeat/entrypoints/cli/_modelo_projection_cli.py`
- `src/aeat/entrypoints/cli/_modelo_rendering.py`
- `src/aeat/entrypoints/cli/_modelo_work_runs_cli.py`

## Description

- Run exact `rg` audit for moved business-policy tokens in changed modelo CLI modules.
- Run exact `rg` audit for extracted modules importing `_modelo.py` or private application modules.
- Run exact `rg` audit for residual private-domain imports in changed CLI modules.
- Run exact `rg` audit for stale row-validation helpers, private M036/IVA wallet imports, and dead casilla-normalisation helpers.

## Outcome

- No changed extracted module imports `_modelo.py`.
- No changed extracted module imports private application modules.
- No changed CLI module contains stale `_validate_m184_share_sum`, `_validate_m347_threshold`,
  `_normalise_casilla_key`, `_casilla_revision_for_work_unit`, `_taxpayer_nif_for_bucket`,
  or private `_m036_lifecycle` imports.
- No changed CLI module contains moved business-policy tokens for applicability, deadline recovery,
  calculation persistence, taxation comparison, maritime fact resolution, or result/plazo summary policy.
- Remaining private-domain imports are known residuals in legacy `_modelo.py` plus the explicit maritime `RentaValidationError` input-validation catch.

## Notes

- The legacy `_modelo.py` root still imports some domain internals pending further command extraction.
- Exact audit still surfaces two registry-authority reads in `_modelo.py` (`resources().modelos.authority`), used by legacy registry introspection/query construction. These are residual debt, not the work/calculate natural-key path.
- The W06.P20 static architecture guard prevents new extracted modules from adding untracked private-domain imports.

Verification:
- `rg -n -g "_modelo*.py" -g "!_modelo_payloads.py" "application\\.modelo\\._|from \\.\\._|_taxpayer_nif_for_bucket|taxpayer_nif_for_bucket|_m036_lifecycle|_validate_m184_share_sum|_validate_m347_threshold|validate_m184_member_share_sum|validate_m347_threshold|M347_THRESHOLD_EUR|_normalise_casilla_key|_casilla_revision_for_work_unit" src/aeat/entrypoints/cli` - no matches.
- `rg -n -g "_modelo*.py" -g "!_modelo_payloads.py" "_service\\(\\)\\._authority|resources\\(\\)\\.modelos\\.authority|authority\\.snapshot|calculate_modelo_revision_from_bucket_aggregation|seed_iva_compensation_period\\(|record_m036_declaration\\(|resolve_maritime_exemption\\(|compare_modelo_years\\(|project_modelo_100_from_m130\\(" src/aeat/entrypoints/cli` - expected application-service calls plus two legacy registry-authority reads.
