---
tags:
  - '#exec'
  - '#application-sign-in'
date: '2026-10-04'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:1c210df07a037c7a1416cdc4ee4279d55e03562eb6847d6d464e2f289b844c15'
related:
  - "[[2026-10-04-application-sign-in-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `application-sign-in` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S01` `M` `dev/agent_eval/tests/test_mcp_frontend_session_lock_parity.py`
- `S01` `M` `dev/agent_eval/tests/test_runtime_automation_grant_lock_parity.py`
- `S01` `M` `dev/docs/sequences/runtime_fixture.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/linux_login.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/login_policy.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/macos_login.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/tests/test_linux_gnome_lock.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/tests/test_linux_login.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/tests/test_login_policy.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/tests/test_macos_login.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/tests/test_posix_login_capture.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/tests/test_windows_login.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/tests/test_windows_login_inventory.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/tests/test_windows_login_inventory_native.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/windows_login.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/enrollment_support.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_session_authority.py`
- `S01` `M` `src/cadrumo/application/auth/tests/test_passphrase_operation_access.py`
- `S01` `M` `src/cadrumo/application/ledger/tests/test_llm_diagnostics_operation.py`
- `S01` `M` `src/cadrumo/application/live/tests/borrador_100_operation_support.py`
- `S01` `M` `src/cadrumo/application/modelo/tests/m036_operation_support.py`
- `S01` `M` `src/cadrumo/application/tests/test_diagnostics_operation.py`
- `S01` `M` `src/cadrumo/application/user_profile/access_administration.py`
- `S01` `M` `src/cadrumo/application/user_profile/access_contracts.py`
- `S01` `M` `src/cadrumo/application/user_profile/session_authority_core.py`
- `S01` `M` `src/cadrumo/application/user_profile/session_authority_policy.py`
- `S01` `M` `src/cadrumo/application/user_profile/tests/test_access_policy.py`
- `S01` `M` `src/cadrumo/application/user_profile/tests/test_automation_inventory_operation.py`
- `S01` `M` `src/cadrumo/application/user_profile/tests/test_history_operation.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/isolated_storage_fixture.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_access_management_native.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_api_key_authentication.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_automation_change_native.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_automation_create_native.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_automation_decision_native.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_automation_list_native.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_login.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_profile_view.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/tests/portable_human_cli_runtime.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/tests/test_runtime_modelo_metadata.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/enrollment_offer.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/profile_connection_access.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/profile_connection_admission.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_access_management.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_automation_approval.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_automation_decision_client.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_automation_enrollment.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_automation_inventory.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_automation_inventory_client.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_descendants_operation.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_enrollment_lifecycle.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_frontend_client.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_login_lifecycle.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_modelo_metadata.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_modelo_metadata_history.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_operation_secret.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_plantilla_media_client.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_profile_binding_retirement.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_profile_connections.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_profile_mutation_client.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_profile_patch_client.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_profile_status_client.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_refusal_detail_authority.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_response_scope.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_runtime_password_rotation.py`
- `S01` `M` `src/cadrumo/entrypoints/tests/test_runtime_credentials.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/tests/test_declarations_installed_create.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/operations/tests/test_runtime_controller.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_runtime_automation_decision.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_runtime_automation_requester_native.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_runtime_password_rotation.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_runtime_reference_login.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_runtime_workbench_native.py`
- `S01` `verify:` `observer and access-policy pytest 259 passed 14 platform-skipped` -> `pass`
- `S01` `verify:` `pytest --collect-only over touched test modules 340 collected 0 errors` -> `pass`
- `S01` `verify:` `ruff check and format --check on 73 files` -> `pass`
- `S01` `verify:` `just check-types` -> `pass`
- `S01` `verify:` `just check-import-boundaries` -> `fail`
- `S02` `A` `src/cadrumo/adapters/persistence/storage/custody/sign_in_generation.py`
- `S02` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/test_sign_in_generation.py`
- `S02` `M` `src/cadrumo/core/storage_taxonomy.py`
- `S02` `M` `src/cadrumo/core/storage_taxonomy_locations.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/storage_path_definitions.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/tests/test_storage_path_directory_agreement_gate.py`
- `S02` `verify:` `focused custody and taxonomy pytest 126 passed` -> `pass`
- `S02` `verify:` `ruff check and format --check; ty win32 linux darwin` -> `pass`
- `S02` `verify:` `just check-persistence-write-paths and check-secure-store-write-paths` -> `pass`
- `S02` `verify:` `just check-module-reachability (alone)` -> `fail`
- `S02` `verify:` `just check-import-boundaries` -> `fail`

## Notes

- `S01` Import-boundary gate reported unavailable because the governed tree changed mid-run; its findings name no touched file. Four unrelated test failures came from other writers' in-progress journal and label repository edits and passed when rerun alone. Mixed-owner files committed with only the lock-state hunks.
- `S02` Reachability is red only until P01.S03 consumes the module; S03 lands in the next commit and its reachability run passes. Import gate failed on 44 findings in other writers' files plus a mid-run tree change. Record kept in the keystore beside the receipt and throttle, since .automation-v1 is cleared on automation retirement; value is lineage plus counter so an unreadable record can be repaired without reusing an issued generation. Taxonomy files committed with only this Step's hunks.
