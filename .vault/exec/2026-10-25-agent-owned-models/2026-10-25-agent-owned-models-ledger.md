---
tags:
  - '#exec'
  - '#agent-owned-models'
date: '2026-10-25'
modified: '2026-10-25'
body_schema: 'body-v2'
body_hash: 'sha256:ac1db169f5aa924ae80716f0fda88af4bf50a9492a11910b3626aaa408d87348'
related:
  - "[[2026-10-25-agent-owned-models-plan]]"
---

# `agent-owned-models` ledger

## Changes

- `S06` `D` `src/cadrumo/domain/transactions/model_tier.py`
- `S06` `M` `src/cadrumo/domain/transactions/llm.py`
- `S06` `M` `src/cadrumo/domain/transactions/__init__.py`
- `S06` `M` `dev/quality/metadata/import_load_targets.json`
- `S06` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S06` `verify:` `ruff check+format` -> `pass`
- `S06` `verify:` `ty check src/cadrumo/domain/transactions` -> `pass`
- `S06` `verify:` `lint-imports` -> `pass`
- `S06` `verify:` `pytest src/cadrumo/domain/transactions dev/quality/tests/test_import_load_worker.py` -> `pass`
- `S06` `by:` `implementer`
- `S07` `A` `dev/quality/tests/test_no_model_definitions.py`
- `S07` `verify:` `ruff check+format` -> `pass`
- `S07` `verify:` `ty check dev/quality/tests/test_no_model_definitions.py` -> `pass`
- `S07` `verify:` `lint-imports` -> `pass`
- `S07` `verify:` `pytest dev/quality/tests/test_no_model_definitions.py` -> `pass`
- `S07` `by:` `implementer`
- `S01` `M` `src/cadrumo_agent_service/providers/domain/record.py`
- `S01` `M` `src/cadrumo_agent_service/providers/persistence/store.py`
- `S01` `M` `src/cadrumo_agent_service/providers/application/ports.py`
- `S01` `M` `src/cadrumo_agent_service/providers/application/tests/memory_store.py`
- `S01` `A` `src/cadrumo_agent_service/providers/persistence/tests/test_store_role_selections.py`
- `S01` `verify:` `uv run --no-sync pytest -q -p no:cacheprovider src/cadrumo_agent_service dev/quality/tests/test_secure_store_write_path.py` -> `pass`
- `S01` `verify:` `uv run --no-sync lint-imports --config .importlinter --no-cache` -> `pass`
- `S01` `verify:` `ruff check/format, ty check on touched files` -> `pass`
- `S01` `verify:` `python -m dev.operation_contract_manifest.generate --check` -> `pass`
- `S01` `by:` `vaultspec-high-executor`
- `S02` `M` `src/cadrumo_agent_service/providers/application/model_runs.py`
- `S02` `M` `src/cadrumo_agent_service/providers/application/tests/test_model_runs.py`
- `S02` `M` `src/cadrumo_agent_service/service.py`
- `S02` `verify:` `uv run --no-sync pytest -q -p no:cacheprovider src/cadrumo_agent_service` -> `pass`
- `S02` `verify:` `pytest dev/runtime_lifecycle/tests/test_service_model_run_relay.py dev/quality/tests/test_no_model_definitions.py dev/quality/tests/test_secure_store_write_path.py` -> `pass`
- `S02` `verify:` `uv run --no-sync lint-imports --config .importlinter --no-cache` -> `pass`
- `S02` `verify:` `ruff check/format, ty check on touched files` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `M` `src/cadrumo_agent_service/admin.py`
- `S03` `M` `src/cadrumo_agent_service/service.py`
- `S03` `M` `src/cadrumo_agent_service/providers/application/contracts.py`
- `S03` `M` `src/cadrumo_agent_service/providers/application/service.py`
- `S03` `A` `src/cadrumo_agent_service/providers/application/tests/test_model_role_selections.py`
- `S03` `M` `src/cadrumo_agent_service/host/tests/test_admin_authority.py`
- `S03` `M` `dev/runtime_lifecycle/tests/test_service_provider_admin_ingress.py`
- `S03` `verify:` `pytest -m "(unit or integration) and not serial ..." src/cadrumo_agent_service dev/runtime_lifecycle/tests/test_service_provider_admin_ingress.py dev/runtime_lifecycle/tests/test_service_model_run_relay.py` -> `pass`
- `S03` `verify:` `uv run --no-sync lint-imports --config .importlinter --no-cache` -> `pass`
- `S03` `verify:` `ruff check/format, ty check on touched files` -> `pass`
- `S03` `verify:` `python -m dev.operation_contract_manifest.generate --check` -> `pass`
- `S03` `by:` `vaultspec-high-executor`
- `S04` `M` `src/cadrumo_client/contracts/model_runs.py`
- `S04` `M` `src/cadrumo_client/contracts/tests/test_model_runs.py`
- `S04` `M` `src/cadrumo_runtime/contracts/worker_authorization.py`
- `S04` `M` `src/cadrumo_runtime/adapters/worker_authorization_lease.py`
- `S04` `M` `src/cadrumo_runtime/host/profile_connection_model_runs.py`
- `S04` `M` `src/cadrumo_runtime/host/operation_authority.py`
- `S04` `M` `src/cadrumo_runtime/host/tests/test_model_run_authority.py`
- `S04` `M` `src/cadrumo/application/operations/model_runs.py`
- `S04` `M` `src/cadrumo/application/operations/tests/test_model_runs.py`
- `S04` `M` `src/cadrumo/adapters/outbound/llm/tests/model_run_support.py`
- `S04` `M` `src/cadrumo_agent_service/providers/application/model_runs.py`
- `S04` `M` `src/cadrumo_agent_service/providers/application/tests/test_model_runs.py`
- `S04` `M` `src/cadrumo_agent_service/host/model_run_relay.py`
- `S04` `M` `dev/runtime_lifecycle/tests/test_service_model_run_relay.py`
- `S04` `verify:` `pytest -m "(unit or integration) and not serial ..." over client contracts, runtime model-run and worker-authorization tests, operations model runs, llm tests, agent service and the service model-run relay (1632 tests)` -> `pass`
- `S04` `verify:` `uv run --no-sync lint-imports --config .importlinter --no-cache` -> `pass`
- `S04` `verify:` `ruff check/format, ty check on touched files and packages` -> `pass`
- `S04` `verify:` `python -m dev.operation_contract_manifest.generate --check` -> `pass`
- `S04` `verify:` `pytest dev/quality/tests/test_no_model_definitions.py` -> `pass`
- `S04` `by:` `vaultspec-high-executor`
- `S05` `A` `native/desktop/src-tauri/src/agent/model_roles.rs`
- `S05` `M` `native/desktop/src-tauri/src/agent/mod.rs`
- `S05` `M` `native/desktop/src-tauri/src/agent/admin.rs`
- `S05` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S05` `verify:` `rustfmt --edition 2024 --check src/agent/model_roles.rs src/agent/mod.rs src/agent/admin.rs` -> `pass`
- `S05` `verify:` `cargo test and cargo clippy -D warnings on model_roles.rs in an isolated scratch crate (serde, serde_json, stubbed is_provider_id)` -> `pass`
- `S05` `verify:` `npx tsc --noEmit, eslint and prettier --check on src/ipc/contract.ts` -> `pass`
- `S05` `verify:` `pytest dev/quality/tests/test_no_model_definitions.py dev/quality/tests/test_no_git_cli.py` -> `pass`
- `S05` `by:` `vaultspec-high-executor`
- `S29` `M` `src/cadrumo_agent_service/providers/persistence/store.py`
- `S29` `M` `src/cadrumo_agent_service/providers/application/ports.py`
- `S29` `M` `src/cadrumo_agent_service/providers/application/service.py`
- `S29` `M` `src/cadrumo_agent_service/providers/application/model_runs.py`
- `S29` `M` `src/cadrumo_agent_service/providers/domain/record.py`
- `S29` `M` `src/cadrumo_agent_service/service.py`
- `S29` `M` `src/cadrumo_agent_service/providers/application/tests/memory_store.py`
- `S29` `M` `src/cadrumo_agent_service/providers/application/tests/test_model_runs.py`
- `S29` `M` `src/cadrumo_agent_service/providers/application/tests/test_model_role_selections.py`
- `S29` `M` `src/cadrumo_agent_service/providers/persistence/tests/test_store_role_selections.py`
- `S29` `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `S29` `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `S29` `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `S29` `M` `dev/packaging/native/service_descriptors.py`
- `S29` `M` `dev/packaging/native/tests/test_service_descriptors.py`
- `S29` `M` `dev/runtime_lifecycle/tests/provider_catalog_support.py`
- `S29` `M` `dev/runtime_lifecycle/tests/test_service_provider_admin_ingress.py`
- `S29` `M` `native/CONTRACT.md`
- `S29` `M` `.vault/adr/2026-10-25-agent-owned-models-adr.md`
- `S29` `A` `src/cadrumo_agent_service/providers/application/model_role_selections.py`
- `S29` `verify:` `uv run --no-sync pytest src/cadrumo_agent_service` -> `pass`
- `S29` `verify:` `uv run --no-sync pytest -m '' dev/runtime_lifecycle/tests/test_service_provider_admin_ingress.py dev/runtime_lifecycle/tests/test_service_model_run_relay.py` -> `pass`
- `S29` `verify:` `uv run --no-sync pytest dev/quality/tests/test_secure_store_write_path.py src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py dev/packaging/native/tests/test_service_descriptors.py dev/packaging/tests/test_native_service_descriptors.py` -> `pass`
- `S29` `verify:` `uv run --no-sync lint-imports --config .importlinter --no-cache` -> `pass`
- `S29` `verify:` `uv run --no-sync python -m dev.operation_contract_manifest.generate --check` -> `pass`
- `S29` `verify:` `uv run --no-sync python -m dev.quality.types` -> `pass`
- `S29` `by:` `vaultspec-high-executor`

## Notes

- `S03` Wire result shapes live in providers/application/contracts.py beside the provider status shapes; `src/cadrumo_agent_service/contracts.py` needed no change.
- `S04` The selections read crosses the `cadrumo_client` wire contract, the runtime worker instruction and lease, and the operation authority as well as the three named files.
- `S05` The desktop crate was not compiled here; mod.rs and admin.rs edits are not compiler-verified. gateway.rs needed no change: the selection is served by the service admin endpoint, not the agent gateway.
- `S29` Installed packages need a rebuild before the installed runtime admits the model-role-selections capability; the descriptor is staged at assembly.
