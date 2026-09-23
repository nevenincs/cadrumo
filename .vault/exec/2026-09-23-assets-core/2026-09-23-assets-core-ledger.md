---
tags:
  - '#exec'
  - '#assets-core'
date: '2026-09-23'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:289b23d8cdef5a7acae3bc9b612b7d562d90c06d3c98b9ed43582f710ea70f9a'
related:
  - "[[2026-09-23-assets-core-plan]]"
---

# `assets-core` ledger

## Changes

- `S01` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/legal/is.toml`
- `S01` `verify:` `publish-authority logical_generation 4fa84c26a651` -> `pass`
- `S01` `by:` `assets-core`
- `S02` `A` `src/cadrumo/domain/renta/actividad_asset/election.py`
- `S02` `M` `src/cadrumo/domain/renta/actividad_asset/lifecycle.py`
- `S02` `M` `src/cadrumo/domain/renta/actividad_asset/schedule.py`
- `S02` `M` `src/cadrumo/domain/renta/actividad_asset/claims.py`
- `S02` `verify:` `basedpyright pyrefly ty strict on changed domain files` -> `pass`
- `S02` `by:` `assets-core`
- `S03` `M` `src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py`
- `S03` `verify:` `real-registry resolver suite 33 tests` -> `pass`
- `S03` `by:` `assets-core`
- `S04` `M` `src/cadrumo/application/actividad_asset/operations.py`
- `S04` `M` `src/cadrumo/application/actividad_asset/ports.py`
- `S04` `A` `src/cadrumo/application/actividad_asset/modality.py`
- `S04` `M` `src/cadrumo/application/calculations/actividad_asset_schedule.py`
- `S04` `verify:` `asset unit suites 86 tests` -> `pass`
- `S04` `by:` `assets-core`
- `S05` `M` `src/cadrumo/entrypoints/cli/_actividad_asset_cli.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/_app_ledger_actividad_asset_command_specs.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/ledger/actividad_asset.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/ledger/models_actividad_asset.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `S05` `M` `src/cadrumo/locales/en/cli.yml`
- `S05` `M` `src/cadrumo/locales/es/cli.yml`
- `S05` `M` `src/cadrumo/locales/ca/cli.yml`
- `S05` `M` `src/cadrumo/locales/hu/cli.yml`
- `S05` `M` `dev/quality/metadata/import_load_targets.json`
- `S05` `verify:` `locale namespace parity for actividad_asset` -> `pass`
- `S05` `by:` `assets-core`
- `S06` `M` `dev/registry/tests/test_activity_asset_schedule_authority_resolution.py`
- `S06` `M` `src/cadrumo/domain/renta/actividad_asset/tests/test_lifecycle.py`
- `S06` `M` `src/cadrumo/domain/renta/actividad_asset/tests/test_free_depreciation.py`
- `S06` `M` `src/cadrumo/application/actividad_asset/tests/test_operations.py`
- `S06` `verify:` `focused suite against generation 4fa84c26 57 tests` -> `pass`
- `S06` `by:` `assets-core`
- `S07` `A` `dev/acceptance/assets/installed_method_proof.py`
- `S07` `M` `dev/acceptance/assets/installed_tui_child.py`
- `S07` `M` `dev/acceptance/assets/installed_journey.py`
- `S07` `M` `dev/acceptance/assets/installed_profile_setup.py`
- `S07` `M` `dev/acceptance/assets/export_journey.py`
- `S07` `M` `dev/acceptance/assets/evidence.py`
- `S07` `M` `dev/acceptance/assets/tests/test_evidence.py`
- `S07` `M` `dev/acceptance/assets/tests/test_installed_journey.py`
- `S07` `A` `dev/acceptance/assets/tests/test_installed_tui_child.py`
- `S07` `M` `dev/quality/metadata/import_load_targets.json`
- `S07` `M` `src/cadrumo/application/actividad_asset/operations.py`
- `S07` `M` `src/cadrumo/application/actividad_asset/history.py`
- `S07` `M` `src/cadrumo/entrypoints/cli/_actividad_asset_cli.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/ledger/actividad_asset.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/ledger/tests/test_actividad_asset_parity.py`
- `S07` `verify:` `asset suites 105 tests` -> `pass`
- `S07` `by:` `assets-core`
- `S09` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml`
- `S09` `M` `src/cadrumo/_data/registry/aeat/legal/is.toml`
- `S09` `M` `src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py`
- `S09` `M` `src/cadrumo/domain/renta/actividad_asset/election.py`
- `S09` `M` `src/cadrumo/domain/renta/actividad_asset/lifecycle.py`
- `S09` `A` `src/cadrumo/domain/renta/actividad_asset/vehicle_affectation.py`
- `S09` `M` `dev/registry/tests/test_activity_asset_schedule_authority_resolution.py`
- `S09` `M` `dev/quality/metadata/import_load_targets.json`
- `S09` `verify:` `asset suites 112 tests` -> `pass`
- `S09` `by:` `assets-core`
- `S10` `M` `src/cadrumo/application/operator_actions/catalogue.py`
- `S10` `M` `src/cadrumo/application/calculations/actividad_asset_schedule.py`
- `S10` `M` `src/cadrumo/domain/renta/actividad_asset/errors.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py`
- `S10` `M` `src/cadrumo/entrypoints/tui/ledger/actividad_asset.py`
- `S10` `M` `src/cadrumo/entrypoints/tui/ledger/tests/test_actividad_asset_parity.py`
- `S10` `M` `src/cadrumo/entrypoints/cli/tests/test_actividad_asset_commands.py`
- `S10` `verify:` `asset suites 110 tests` -> `pass`
- `S10` `by:` `assets-core`
- `S12` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0001-declarations.toml`
- `S12` `D` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml`
- `S12` `verify:` `authoring inspection 0 findings; publish-authority generation dc950e46 sqlite-v3 current` -> `pass`
- `S12` `by:` `assets-core`
- `S11` `A` `src/cadrumo/domain/renta/actividad_asset/workforce.py`
- `S11` `A` `src/cadrumo/domain/renta/actividad_asset/tests/test_workforce.py`
- `S11` `verify:` `workforce unit tests 5` -> `pass`
- `S11` `by:` `assets-core`

## Notes

- `S06` day-count proration differs from AEAT month-based worked examples (EUR 733.81 vs EUR 720 for the LIS art. 103 example); recorded as an inconsistency for a lifecycle-ADR amendment
- `S07` the superseding-claim fixes f92721ce93 and 2f97378e51 postdate wheel 16d5e13e; installed run 3 at 2f97378e51 is queued for the machine-wide installed-run slot
- `S12` installed run 5 at 150f306c8b proves the tree before S10; the final installed proof of HEAD remains open
- `S11` resolver wiring waits for the profile schema version 7 field irpf.plantilla_media

