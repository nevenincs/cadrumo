---
tags:
  - '#exec'
  - '#test-suite-budget'
date: '2026-10-30'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:dd71694bd48d6568dc1337426f97143f06644c25f5cc354347e4b9fa608aa0b2'
related:
  - "[[2026-10-30-test-suite-budget-plan]]"
---

# `test-suite-budget` ledger

## Changes

- `S01` `M` `src/cadrumo/entrypoints/tests/registered_executor_case_support.py`
- `S01` `verify:` `pytest test_operation_subject_binding test_registered_executor_conformance` -> `pass`
- `S02` `M` `src/cadrumo/entrypoints/tests/registered_executor_case_support.py`
- `S02` `verify:` `pytest frontend parity family` -> `pass`
- `S03` `M` `dev/registry/tests/test_condition_overlap.py`
- `S03` `M` `dev/registry/analysis/load_census.py`
- `S03` `M` `dev/registry/tests/test_declaration_invariant_gates.py`
- `S03` `verify:` `pytest registry condition and invariant gates` -> `pass`
- `S04` `M` `dev/tests/test_import_quality_gate.py`
- `S04` `M` `dev/packaging/tests/test_preflight_recipe_selection.py`
- `S04` `M` `dev/tests/test_wheel_content_boundary.py`
- `S04` `M` `dev/locales/tests/conftest.py`
- `S04` `M` `dev/quality/docstring_reference_targets.py`
- `S04` `M` `dev/quality/tests/test_docstring_reference_targets.py`
- `S04` `verify:` `pytest import gate, preflight, wheel boundary` -> `pass`
- `S05` `M` `src/cadrumo/entrypoints/tui/tests/test_workbench_acceptance.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_records_real.py`
- `S05` `M` `dev/tui/harness/sequences.py`
- `S05` `M` `dev/tui/harness/tests/test_sequence_scenarios.py`
- `S05` `verify:` `pytest tui acceptance and records` -> `pass`
- `S06` `M` `src/cadrumo/adapters/persistence/profile/modelos_calculation.py`
- `S06` `M` `src/cadrumo/adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py`
- `S06` `M` `src/cadrumo/domain/modelos/calculation_revision_rendering.py`
- `S06` `M` `src/cadrumo/domain/modelos/tests/test_calculation_rendering_registry_memo.py`
- `S06` `M` `src/cadrumo/domain/modelos/tests/test_calculation_rendering_serializer_memo.py`
- `S06` `M` `src/cadrumo/adapters/persistence/profile/calculation_revision_override_migration.py`
- `S06` `M` `src/cadrumo/adapters/persistence/profile/tests/test_calculation_revision_override_migration.py`
- `S06` `verify:` `pytest calculation rendering and refusal tests` -> `pass`
- `S07` `M` `dev/registry/conftest.py`
- `S07` `M` `dev/docs/sequences/sandbox.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/profile_registration.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/test_sealed_profile_world.py`
- `S07` `M` `src/cadrumo/adapters/persistence/storage/tests/seeded_isolated_backend_fixture.py`
- `S07` `M` `src/cadrumo_runtime/host/tests/frontend/cli/runtime_profile_backend.py`
- `S07` `M` `src/cadrumo_runtime/host/tests/frontend/cli/test_machine_secret_channels_subprocess.py`
- `S07` `M` `src/cadrumo_runtime/host/tests/frontend/cli/world_provider.py`
- `S07` `M` `src/cadrumo_runtime/host/tests/frontend/cli/test_ledger_bulk_classify.py`
- `S07` `M` `src/cadrumo_runtime/host/tests/native_commands/runtime_profile_cli_fixture.py`
- `S07` `M` `src/cadrumo/adapters/persistence/profile/tests/sealed_profile_world.py`
- `S07` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/enrollment_support.py`
- `S07` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_automation_store.py`
- `S07` `M` `src/cadrumo_runtime/application/tests/test_session_authority.py`
- `S07` `verify:` `pytest sealed profile world and consumers` -> `pass`
- `S07` `M` `src/cadrumo_runtime/host/tests/frontend/cli/config/tests/isolated_storage_fixture.py`
- `S07` `verify:` `pytest test_profile_lifecycle_verbs test_active_profile_env_override_name` -> `pass`
- `S15` `A` `.vault/audit/2026-10-31-test-suite-budget-cli-file-operations-audit.md`

## Notes

- `S15` Diagnosis only, no fix built
