---
tags:
  - '#exec'
  - '#agent-owned-models'
date: '2026-10-25'
modified: '2026-10-25'
body_schema: 'body-v2'
body_hash: 'sha256:22f6021f60d8a1c35b3f6b7441ce47a9ea499c2cb1d7a61187096d854e872381'
related:
  - "[[2026-10-25-agent-owned-models-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `agent-owned-models` ledger

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

## Notes

- `S03` Wire result shapes live in providers/application/contracts.py beside the provider status shapes; `src/cadrumo_agent_service/contracts.py` needed no change.
- `S04` The selections read crosses the `cadrumo_client` wire contract, the runtime worker instruction and lease, and the operation authority as well as the three named files.
