---
tags:
  - '#exec'
  - '#application-sign-in'
date: '2026-10-04'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:0a19c4ab9b7405b5e921067e0bb48a4dda853af96dfae6ab1a2c279dfa7068a9'
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
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt_crypto.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/profile_login_session.py`
- `S03` `M` `src/cadrumo/application/user_profile/login_session_port.py`
- `S03` `M` `src/cadrumo/application/user_profile/login_session.py`
- `S03` `M` `src/cadrumo/entrypoints/runtime/profile_login.py`
- `S03` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/receipt_sign_in.py`
- `S03` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_sign_in_binding.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_candidate_receipt_publication.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_supplied_human_receipt.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_custody_transactions.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_passphrase_replacement_contract.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/tests/test_profile_login_session_adapter.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/tests/test_test_support_runtime_context_lifecycle.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_login_handover.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_login.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_logout.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_cli_commands_leave_no_unsealed_bucket_session.py`
- `S03` `M` `src/cadrumo/entrypoints/runtime/tests/test_receipt_login.py`
- `S03` `verify:` `custody, storage, master_key, user_profile pytest not os_keychain 2214 passed 142 skipped` -> `pass`
- `S03` `verify:` `ruff check and format --check; ty win32 linux darwin` -> `pass`
- `S03` `verify:` `just check-module-reachability` -> `pass`
- `S03` `verify:` `just check-persistence-write-paths and check-secure-store-write-paths` -> `pass`
- `S03` `verify:` `runtime and CLI receipt suites 103 passed 17 failed` -> `fail`
- `S04` `M` `src/cadrumo/entrypoints/runtime/session_owner.py`
- `S04` `M` `src/cadrumo/entrypoints/runtime/profile_login.py`
- `S04` `M` `src/cadrumo/application/user_profile/session_authority_admission.py`
- `S04` `M` `src/cadrumo/application/user_profile/session_authority_contracts.py`
- `S04` `M` `src/cadrumo/entrypoints/runtime/worker_service.py`
- `S04` `M` `src/cadrumo/application/runtime/profile_worker.py`
- `S04` `M` `src/cadrumo/adapters/local_runtime/profile_worker_human_admission.py`
- `S04` `M` `src/cadrumo/application/user_profile/login_session.py`
- `S04` `M` `src/cadrumo/application/user_profile/login_session_port.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/profile_login_session.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/sign_in_generation.py`
- `S04` `M` `src/cadrumo/entrypoints/runtime/tests/test_receipt_login.py`
- `S04` `M` `src/cadrumo/entrypoints/runtime/tests/test_human_login_receipt.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_session_authority.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_sign_in_binding.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_candidate_receipt_publication.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/tests/test_profile_login_session_adapter.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/receipt_sign_in.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_custody_transactions.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_passphrase_replacement_contract.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_supplied_human_receipt.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/tests/test_test_support_runtime_context_lifecycle.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_login.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_logout.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/tests/test_cli_commands_leave_no_unsealed_bucket_session.py`
- `S04` `verify:` `binding, generation, adapter, candidate-publication, session-authority pytest 118 passed` -> `pass`
- `S04` `verify:` `real runtime+worker mint-ordering scenarios (refused publication, retired before mint, generation advanced, success)` -> `pass`
- `S04` `verify:` `ruff check and format --check; ty win32 linux darwin` -> `pass`
- `S04` `verify:` `just check-module-reachability; check-persistence-write-paths; registry enforcement` -> `pass`
- `S04` `verify:` `runtime directory -n 3 (13 failed 1 error; 4 reproduce alone and predate this Step)` -> `fail`
- `S05` `M` `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py`
- `S05` `M` `src/cadrumo/adapters/local_runtime/frontend_client.py`
- `S05` `M` `src/cadrumo/application/user_profile/login_session.py`
- `S05` `M` `src/cadrumo/application/user_profile/login_session_port.py`
- `S05` `M` `src/cadrumo/adapters/persistence/storage/profile_login_session.py`
- `S05` `M` `src/cadrumo/application/runtime/profile_worker.py`
- `S05` `M` `src/cadrumo/adapters/local_runtime/profile_worker_human_admission.py`
- `S05` `M` `src/cadrumo/entrypoints/runtime/session_owner.py`
- `S05` `M` `src/cadrumo/entrypoints/runtime/profile_login.py`
- `S05` `M` `src/cadrumo/entrypoints/runtime/worker_service.py`
- `S05` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/test_frontend_receipt_borrow_is_proof_only.py`
- `S05` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_supplied_human_receipt.py`
- `S05` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_candidate_receipt_publication.py`
- `S05` `M` `src/cadrumo/entrypoints/runtime/tests/test_receipt_login.py`
- `S05` `M` `src/cadrumo/entrypoints/runtime/tests/test_human_login_receipt.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/tests/test_cli_commands_leave_no_unsealed_bucket_session.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_login.py`
- `S05` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/receipt_binding_probe.py`
- `S05` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_sign_in_binding.py`
- `S05` `verify:` `focused pytest on touched files 100 passed` -> `pass`
- `S05` `verify:` `custody 1027 passed; user_profile 578 passed` -> `pass`
- `S05` `verify:` `gate: frontend borrow made deleting fails the proof-only test` -> `pass`
- `S05` `verify:` `real-worker login mismatch and generation change refuse and delete runtime-side` -> `pass`
- `S05` `verify:` `ruff; ty win32 linux darwin; just check-types` -> `pass`
- `S05` `verify:` `check-module-reachability, persistence and secure-store write paths` -> `pass`
- `S05` `verify:` `application/runtime + CLI/TUI login suites 189 passed 3 failed` -> `fail`

## Notes

- `S01` Import-boundary gate reported unavailable because the governed tree changed mid-run; its findings name no touched file. Four unrelated test failures came from other writers' in-progress journal and label repository edits and passed when rerun alone. Mixed-owner files committed with only the lock-state hunks.
- `S02` Reachability is red only until P01.S03 consumes the module; S03 lands in the next commit and its reachability run passes. Import gate failed on 44 findings in other writers' files plus a mid-run tree change. Record kept in the keystore beside the receipt and throttle, since .automation-v1 is cleared on automation retirement; value is lineage plus counter so an unreadable record can be repaired without reusing an issued generation. Taxonomy files committed with only this Step's hunks.
- `S03` The 17 runtime/CLI failures precede login `(runtime_unavailable` without a started runtime, a desktop webview directory, a placeholder logout text) and do not reach this change. `os_keychain` tests cannot run here (Credential Manager error 1312 in this logon session) and need an interactive desktop run. Legacy in-process login no longer mints receipts; P03.S12 retires it and the now-vacuous handover keyring-failure test. Mint order unchanged; S04 moves it after publication.
- `S04` Mint now runs after publication under the admission guard with the generation captured at publication; `require_current` refuses a moved record before any write. The worker holds the password proof as a pending receipt from bind to mint (a DEK copy for that window). Remaining failures predate this Step in earlier run logs `(runtime_unavailable` resume tests, modelo revision lifecycle, automation approval renew, operation secret tui export, worker drain) or pass alone under less load. `os_keychain` tests not run (Credential Manager error 1312 in this logon session). New internal runtime-worker request `mint_human_receipt;` scope corrected in the plan.
- `S05` Carries the reachability-burndown S07 receipt API move (verify/classify API to `tests/receipt_binding_probe.py` and its two rewritten tests), already logged in that ledger, because it is intertwined with this Step and was verified together. Remaining failures: one `runtime_unavailable` test failing before this Step, one intermittent OpenProcess 87, one leaked-patch failure seen in earlier runs. Login and generation refusals reach clients coarsely until S09. Remaining non-runtime unwrap callers `(bind_resumed_profile_session,` `_resume_for_idempotent_login` via `_profile_session_gate` and `session_admission)` are for P03.S12. S07 must recheck the generation at publication against a sign-out between the worker check and publication.
