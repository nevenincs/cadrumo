---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:c3959931b06d5fe87bf3f1f64912be08f2dc9c07bd483970da775cb43d951c43'
step_id: 'S11'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Update the operator-actions catalogue target command key

## Scope

- `src/cadrumo/application/operator_actions/`

## Changes

- `M` `src/cadrumo/application/operator_actions/_catalogue.py`
- `M` `src/cadrumo/application/operator_surface/_contract.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_repair_prepared_exports.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_repair_prepared_exports_payloads.py`
- `R` `src/cadrumo/entrypoints/cli/tests/test_app_maintenance_command_specs.py` -> `src/cadrumo/entrypoints/cli/tests/test_config_repair_prepared_exports_command_specs.py`
- `R` `src/cadrumo/entrypoints/cli/tests/test_app_maintenance_export_reconcile.py` -> `src/cadrumo/entrypoints/cli/tests/test_config_repair_prepared_exports.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_root_cli_action_producer_census.py`
- `M` `src/cadrumo/tests/test_every_module_has_test_coverage.py`
- `verify:` `pytest operator_surface/tests + repointed cli tests` -> `pass`

## Notes

`test_every_production_module_is_exercised_by_a_test` remains red on modules
outside this Step's scope (`adapters/outbound/aeat/browser/health.py`,
`core/storage_route_guidance.py`, `domain/fincas/_source_readiness.py` and
siblings). The two entries this Step repointed are no longer flagged.
