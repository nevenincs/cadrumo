---
tags:
  - '#exec'
  - '#ephemeral-operations'
date: '2026-10-14'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:18f066db71cdbbc4adaf78dcdf55f5cccf4b05b89d34d477d283be3fa70bf819'
related:
  - "[[2026-10-14-ephemeral-operations-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `ephemeral-operations` ledger

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

- `S01` `A` `src/cadrumo/adapters/persistence/operations/ephemeral_store.py`
- `S01` `A` `src/cadrumo/adapters/persistence/operations/tests/test_ephemeral_store.py`
- `S01` `M` `src/cadrumo/adapters/persistence/operations/journal.py`
- `S01` `verify:` `pytest src/cadrumo/adapters/persistence/operations/tests/test_ephemeral_store.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py` -> `pass`
- `S01` `by:` `vaultspec-high-executor`
- `S02` `A` `src/cadrumo/adapters/persistence/operations/durability_router.py`
- `S02` `A` `src/cadrumo/adapters/persistence/operations/tests/test_durability_router.py`
- `S02` `M` `src/cadrumo/application/operations/persistence/journal.py`
- `S02` `M` `src/cadrumo/application/operations/supervisor.py`
- `S02` `M` `src/cadrumo/application/operations/_supervisor_host.py`
- `S02` `M` `src/cadrumo/application/operations/_supervisor_execution.py`
- `S02` `M` `src/cadrumo/application/operations/_supervisor_reconciliation.py`
- `S02` `M` `src/cadrumo/application/operations/_supervisor_submission.py`
- `S02` `M` `src/cadrumo/application/operations/composition.py`
- `S02` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S02` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S02` `M` `dev/quality/metadata/import_load_targets.json`
- `S02` `verify:` `pytest src/cadrumo/application/operations src/cadrumo/adapters/persistence/operations` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `M` `src/cadrumo/adapters/persistence/operations/tests/test_durability_router.py`
- `S03` `M` `.vault/plan/2026-10-14-ephemeral-operations-plan.md`
- `S03` `verify:` `pytest src/cadrumo/adapters/persistence/operations/tests/test_durability_router.py` -> `pass`
- `S03` `by:` `vaultspec-high-executor`
- `S04` `M` `src/cadrumo/application/user_profile/operations.py`
- `S04` `M` `src/cadrumo/application/user_profile/view_operation.py`
- `S04` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S04` `verify:` `just check-operation-contract-manifest` -> `pass`
- `S04` `verify:` `pytest src/cadrumo/application/user_profile src/cadrumo/application/operations src/cadrumo/entrypoints/tests/test_operation_contract_manifest.py src/cadrumo/entrypoints/tests/test_operation_catalogue.py` -> `pass`
- `S04` `by:` `vaultspec-high-executor`
- `S05` `M` `src/cadrumo/adapters/persistence/operations/tests/test_durability_router.py`
- `S05` `M` `src/cadrumo/entrypoints/runtime/tests/test_frontend_client.py`
- `S05` `verify:` `pytest src/cadrumo/adapters/persistence/operations/tests/test_durability_router.py` -> `pass`
- `S05` `verify:` `pytest src/cadrumo/entrypoints/runtime/tests/test_frontend_client.py` -> `pass`
- `S05` `verify:` `pytest dev/docs/sequences/tests/test_runner.py -n 2` -> `pass`
- `S05` `by:` `vaultspec-high-executor`
- `S06` `M` `src/cadrumo/application/operations/_supervisor_submission.py`
- `S06` `M` `src/cadrumo/application/operations/_supervisor_execution.py`
- `S06` `M` `src/cadrumo/application/operations/_supervisor_host.py`
- `S06` `M` `src/cadrumo/application/operations/supervisor.py`
- `S06` `M` `src/cadrumo/application/operations/persistence/journal.py`
- `S06` `M` `src/cadrumo/adapters/persistence/operations/durability_router.py`
- `S06` `M` `src/cadrumo/adapters/persistence/operations/ephemeral_store.py`
- `S06` `M` `src/cadrumo/adapters/persistence/operations/tests/test_durability_router.py`
- `S06` `M` `src/cadrumo/adapters/persistence/operations/tests/test_operation_definitions.py`
- `S06` `A` `src/cadrumo/entrypoints/runtime/tests/test_ephemeral_profile_view.py`
- `S06` `M` `.vault/plan/2026-10-14-ephemeral-operations-plan.md`
- `S06` `verify:` `pytest -m '' src/cadrumo/entrypoints/runtime/tests/test_ephemeral_profile_view.py (fails 0 vs 1 row against the pre-fix submission)` -> `pass`
- `S06` `verify:` `pytest -m '' src/cadrumo/adapters/persistence/operations src/cadrumo/application/operations` -> `pass`
- `S06` `verify:` `pytest -m '' test_operation_provenance.py test_profile_worker_operations.py` -> `pass`
- `S06` `verify:` `ruff check, ruff format` -> `pass`
- `S06` `by:` `vaultspec-high-executor`

## Notes

- `S02` 4 failures in `test_execution_authority.py` and `test_failure_custody_settlement.py` fail identically on HEAD without this Step (caplog record assertions); not caused here
- `S03` Plan correction: no change to `worker_operation_requests.py` or `_projection_read.py` was needed; both services read through the composed router
- `S05` Profile-view docs test under -n 2 passed 3 of 3 runs (15.4 s, 13.0 s, 43.6 s; previously failed at the 60 s view budget). check-types reports 1 diagnostic and check-import-boundaries reports stale load targets, both from another session's uncommitted `agent_process.py` / `agent_diagnostics.py;` none in this plan's files. The packaged TUI overview read is not run here: it reads through the same user-profile.view path that `test_frontend_client.py` exercises with the OVERVIEW page.
- `S06` S06 Code landed in operator checkpoint 7fa669db8b (and the `_supervisor_execution.py` hunk in 1d03ee6f71); this Step's commit carries the ledger and Step close
- `S06` S06 `test_profile_operation_families_have_one_secure_registered_definition_each` failed since S04 (09a9d2cecf) because the view is credential-free; corrected to assert the view's ephemeral contract
- `S06` S06 just check-types reports 3 ty diagnostics in `test_failed_sandbox_logs.py` and `test_provider_cli.py` from other sessions; none in this plan's files
