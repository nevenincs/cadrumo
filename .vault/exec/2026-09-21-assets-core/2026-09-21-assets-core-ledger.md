---
tags:
  - '#exec'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:b3316cc1e950c91ba102fe88f56a4e53d6f4f8c197837b4388d670c05516ca8e'
related:
  - "[[2026-09-21-assets-core-plan]]"
---

# `assets-core` ledger

## Changes

- `S02` `M` `src/cadrumo/application/aggregation/tests/test_renta_ledger.py`
- `S02` `M` `src/cadrumo/application/aggregation/tests/test_inventory_source.py`
- `S02` `verify:` `uv run ruff check two P01.S02 test files` -> `pass`
- `S02` `by:` `assets-stage1-regression`
- `S01` `M` `.vault/reference/2026-09-21-assets-core-ownership-contracts-reference.md`
- `S01` `M` `.vault/research/2026-09-21-assets-core-lifecycle-and-integration-research.md`
- `S01` `M` `.vault/adr/2026-09-21-assets-core-lifecycle-contract-adr.md`
- `S01` `verify:` `vaultspec assets-core focused checks` -> `pass`
- `S01` `by:` `root`
- `S03` `A` `src/cadrumo/domain/renta/actividad_asset/`
- `S03` `A` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml`
- `S03` `A` `dev/registry/tests/test_modelo_100_activity_asset_amortization_parameters.py`
- `S03` `A` `.vault/adr/2026-09-21-assets-core-cost-basis-stages-adr.md`
- `S03` `verify:` `Ruff ty basedpyright` -> `pass`
- `S03` `by:` `OpenAI GPT-5 lead; Terra High domain worker; Terra Max authority audit`
- `S04` `A` `src/cadrumo/application/actividad_asset/`
- `S04` `A` `src/cadrumo/adapters/persistence/profile/actividad_asset.py`
- `S04` `A` `src/cadrumo/adapters/persistence/profile/tests/test_actividad_asset_history.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `S04` `verify:` `global namespace order test` -> `fail`
- `S04` `by:` `OpenAI GPT-5 lead; Terra High persistence worker`
- `S03` `verify:` `uv run pytest -n 0 -m integration dev/registry/tests/test_authoring_candidate_inspection.py` -> `pass`
- `S03` `verify:` `focused asset domain and authority pytest (13 tests)` -> `pass`
- `S04` `verify:` `focused combined P02 pytest (20 tests)` -> `pass`
- `S04` `verify:` `Ruff ty basedpyright git diff --check` -> `pass`
- `S05` `A` `src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py`
- `S05` `A` `src/cadrumo/application/calculations/actividad_asset_schedule.py`
- `S05` `A` `src/cadrumo/application/aggregation/modelo_bindings_actividad_assets.py`
- `S05` `A` `dev/registry/tests/test_activity_asset_schedule_authority_resolution.py`
- `S05` `A` `src/cadrumo/application/aggregation/tests/test_modelo_bindings_actividad_assets.py`
- `S05` `by:` `OpenAI GPT-5 lead; Terra High resolver worker`
- `S06` `verify:` `live asset source mesh tests (11 tests)` -> `pass`
- `S05` `verify:` `asset authority and pure composition tests (7 tests)` -> `pass`
- `S06` `verify:` `surrounding source boundary regression tests (44 tests)` -> `pass`
- `S06` `M` `src/cadrumo/domain/renta/actividad_asset/claims.py`
- `S06` `M` `src/cadrumo/domain/renta/actividad_asset/tests/test_claims.py`
- `S06` `M` `src/cadrumo/application/aggregation/modelo_bindings.py`
- `S06` `M` `src/cadrumo/application/aggregation/modelo_bindings_renta_expenses.py`
- `S06` `M` `src/cadrumo/application/modelo/calculation_action_ports.py`
- `S06` `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `S06` `M` `src/cadrumo/entrypoints/adapter_composition.py`
- `S06` `M` `src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py`
- `S06` `M` `src/cadrumo/adapters/persistence/profile/tests/file_flow_test_support.py`
- `S06` `M` `src/cadrumo/adapters/persistence/profile/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py`
- `S06` `M` `src/cadrumo/adapters/persistence/profile/tests/test_renta_ledger.py`
- `S06` `M` `src/cadrumo/adapters/persistence/profile/tests/test_source_boundary_and_enrollment.py`
- `S06` `by:` `OpenAI GPT-5 lead; Terra High resolver worker`
- `S06` `verify:` `Ruff ty basedpyright git diff --check` -> `pass`
- `S07` `A` `src/cadrumo/application/actividad_asset/iva_linkage.py`
- `S07` `A` `src/cadrumo/application/actividad_asset/tests/test_iva_linkage.py`
- `S07` `by:` `Terra High filing worker; OpenAI GPT-5 lead`
- `S07` `verify:` `focused reciprocal IVA linkage pytest (4 tests)` -> `pass`
- `S09` `A` `src/cadrumo/application/actividad_asset/operations.py`
- `S09` `A` `src/cadrumo/entrypoints/cli/_actividad_asset_cli.py`
- `S09` `A` `src/cadrumo/entrypoints/cli/_app_ledger_actividad_asset_command_specs.py`
- `S09` `M` `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`
- `S10` `A` `src/cadrumo/entrypoints/tui/ledger/actividad_asset.py`
- `S10` `A` `src/cadrumo/entrypoints/tui/ledger/models_actividad_asset.py`
- `S10` `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `S10` `M` `src/cadrumo/entrypoints/tui/ledger/controller.py`
- `S10` `M` `src/cadrumo/entrypoints/tui/ledger/overview.py`
- `S10` `M` `src/cadrumo/entrypoints/tui/ledger/routes.py`
- `S10` `M` `src/cadrumo/entrypoints/tui/ledger/workspace_injection.py`
- `S09-S10` `by:` `Terra High frontend worker; OpenAI GPT-5 lead`
- `S09-S10` `verify:` `focused shared operations, CLI, TUI, and evidence pytest (11 tests)` -> `pass`
- `S09-S10` `verify:` `Ruff ty basedpyright git diff --check` -> `pass`
- `S11` `A` `dev/acceptance/assets/evidence.py`
- `S11` `A` `dev/acceptance/assets/tests/test_evidence.py`
- `S11` `verify:` `wheel build and installed site-packages origin` -> `pass`
- `S11` `verify:` `installed TUI child over isolated encrypted storage` -> `blocked: no terminal child result`

## Notes

- `S04` Global namespace-order tripwire reaches an unrelated concurrent income-lane omission: withholding_workflow is enrolled but absent from that lane's expected tuple. Assets expected-order entry is present.
- `S08` Blocked on concurrent uncommitted IVA-settlement ownership in src/cadrumo/domain/modelos/filing_record.py and the shared verification/export chain; calculation and provenance are proven, validated export is not claimed.
- `S11` Acceptance status is conservative: AS3, AS4, AS5, AS6, AS8, and AS10 are proven; AS1, AS2, AS7, AS9, AS11, and AS12 remain blocked. Reciprocal IVA linkage is not treated as proof of the complete IVA lifecycle, and an installed wheel import is not treated as a completed frontend journey.
