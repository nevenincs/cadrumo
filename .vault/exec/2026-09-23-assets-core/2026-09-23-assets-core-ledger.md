---
tags:
  - '#exec'
  - '#assets-core'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:fc059e058f6f56513a12c2ff9414239c5f778d37d8c860ca53771e1091c3bcfe'
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

## Notes

- `S06` day-count proration differs from AEAT month-based worked examples (EUR 733.81 vs EUR 720 for the LIS art. 103 example); recorded as an inconsistency for a lifecycle-ADR amendment
- `S07` the superseding-claim fixes f92721ce93 and 2f97378e51 postdate wheel 16d5e13e; installed run 3 at 2f97378e51 is queued for the machine-wide installed-run slot

