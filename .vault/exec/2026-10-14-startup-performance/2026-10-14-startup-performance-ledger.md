---
tags:
  - '#exec'
  - '#startup-performance'
date: '2026-10-14'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:8aa357fe09e1ec6c148928c7c619d0410222026e46eb672135a435fb5cada9a0'
related:
  - "[[2026-10-14-startup-performance-plan]]"
---

# `startup-performance` ledger

## Changes

- `S01` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S01` `A` `src/cadrumo/entrypoints/google_export_operation_composition.py`
- `S01` `M` `src/cadrumo/entrypoints/tests/test_google_effect_imports.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/tests/test_google_operation.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_worker_startup_import_graph.py`
- `S01` `verify:` `eager registry parity probe (283 operations, identical contract-set digest, 148 groups)` -> `pass`
- `S01` `verify:` `pytest test_google_effect_imports test_google_operation test_operation_registry_imports test_operation_execution_imports test_operation_composition` -> `pass`
- `S01` `verify:` `pytest test_worker_startup_import_graph::test_the_exclusion_probe_bites` -> `pass`
- `S01` `by:` `implementation-high`
- `S02` `A` `dev/operation_contract_manifest/generate.py`
- `S02` `A` `dev/operation_contract_manifest/tests/test_generate.py`
- `S02` `A` `src/cadrumo/_data/operations/contract_manifest.json`
- `S02` `M` `src/cadrumo/application/operations/contract_manifest.py`
- `S02` `A` `src/cadrumo/application/operations/tests/test_contract_manifest.py`
- `S02` `M` `justfile`
- `S02` `M` `dev/quality/suite.py`
- `S02` `M` `dev/quality/tests/test_suite_gate_table.py`
- `S02` `M` `.importlinter`
- `S02` `M` `dev/quality/metadata/import_load_targets.json`
- `S02` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S02` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S02` `verify:` `just check-operation-contract-manifest` -> `pass`
- `S02` `verify:` `pytest dev/operation_contract_manifest/tests (stale fingerprint, missing operation, absent file planted defects)` -> `pass`
- `S02` `verify:` `pytest application/operations/tests/test_contract_manifest.py; unsorted render planted defect fails 4 of 5` -> `pass`
- `S02` `verify:` `pytest dev/quality/tests/test_suite_gate_table.py test_no_git_cli.py` -> `pass`
- `S02` `verify:` `just check-types` -> `pass`
- `S02` `by:` `implementation-high`
- `S03` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S03` `A` `src/cadrumo/entrypoints/tests/test_operation_contract_manifest.py`
- `S03` `verify:` `pytest entrypoints/tests/test_operation_contract_manifest.py (stale contract, wrong group, unknown group refusals; module-graph gate)` -> `pass`
- `S03` `verify:` `pytest test_google_operation (compose_operation_dependencies on the manifest registry)` -> `pass`
- `S03` `by:` `implementation-high`
- `S04` `M` `src/cadrumo/entrypoints/runtime/profile_connections.py`
- `S04` `M` `src/cadrumo/entrypoints/runtime/tests/test_profile_registry_readiness.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/installed_session.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/tests/test_installed_session.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/tests/test_runtime_admission.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/tests/test_launcher_composition_root.py`
- `S04` `verify:` `pytest test_profile_registry_readiness test_launcher_composition_root test_installed_session test_runtime_admission` -> `pass`
- `S04` `verify:` `just check-import-boundaries` -> `fail`
- `S04` `by:` `implementation-high`

## Notes

- `S01` Commit 311cf0b5a1 was not made by this worker; it swept this Step's uncommitted `google_export_operation_composition.py,` test edits and the plan together with unrelated work under a startup-performance subject. `operation_composition.py` itself landed in 925db5295c.
- `S01` `test_a_ready_worker_excludes_the_operation_graph` fails on `cadrumo.domain.provider_settings.catalog` from the concurrent provider-settings work, not this Step.
- `S02` `dev/operation_contract_manifest/*` was committed in 311cf0b5a1 by another session; the rest landed in 695e89d07f.
- `S02` render() sorted frozenset fields by process hash seed, making the manifest differ between runs; fixed in this Step.
- `S03` Code landed in 925db5295c together with S01 because HEAD consumers swept in 311cf0b5a1 already referenced `build_manifest_operation_registry.`
- `S03` Another agent has an uncommitted edit to `test_operation_contract_manifest.py` widening `_PLATFORM_VARIABLES` with home variables; left for its owner.
- `S04` check-import-boundaries failed only operationally: governed source tree changed while the gate ran (concurrent writers); 0 hard findings, 15/15 contracts kept, 4695/4695 modules load.
- `S04` TUI changes were committed in 311cf0b5a1 by another session; runtime change landed in 631c136366.
