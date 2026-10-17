---
tags:
  - '#exec'
  - '#operation-cues'
date: '2026-10-17'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:2da75d76d5a454906fcc73c15088edc6404bbf491fdb0d70d9bfccee953f8aa6'
related:
  - "[[2026-10-17-operation-cues-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `operation-cues` ledger

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

- `S01` `M` `src/cadrumo/adapters/persistence/operations/durability_router.py`
- `S01` `M` `src/cadrumo/adapters/persistence/operations/tests/test_durability_router.py`
- `S01` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S01` `M` `src/cadrumo_runtime/contracts/worker_authorization.py`
- `S01` `M` `src/cadrumo_runtime/adapters/worker_authorization.py`
- `S01` `M` `src/cadrumo_runtime/adapters/worker_authorization_client.py`
- `S01` `M` `src/cadrumo_runtime/adapters/tests/worker_authorization_fixture.py`
- `S01` `M` `src/cadrumo_runtime/adapters/tests/test_worker_authorization.py`
- `S01` `M` `src/cadrumo_runtime/host/operation_host.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_host.py`
- `S01` `A` `src/cadrumo_runtime/host/operation_progress_reporter.py`
- `S01` `A` `src/cadrumo_runtime/host/tests/test_operation_progress_reporter.py`
- `S01` `verify:` `pytest -m integration test_durability_router.py` -> `pass`
- `S01` `verify:` `pytest test_operation_progress_reporter.py` -> `pass`
- `S01` `verify:` `pytest -m integration test_worker_authorization.py` -> `pass`
- `S01` `verify:` `pytest operation host and persistence suites` -> `pass`
- `S01` `verify:` `ruff check, ruff format --check, ty check, lint-imports` -> `pass`
- `S02` `M` `src/cadrumo_client/contracts/session_events.py`
- `S02` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S02` `M` `src/cadrumo_runtime/host/session_events.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_operations.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_admission.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connection_sessions.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_connections.py`
- `S02` `M` `src/cadrumo_runtime/host/tests/test_connection_cues.py`
- `S02` `verify:` `pytest test_connection_cues.py` -> `pass`
- `S02` `verify:` `pytest -m unit cadrumo_runtime/host/tests cadrumo_client/transport/tests cadrumo_client/contracts` -> `pass`
- `S02` `verify:` `ruff check, ruff format --check, ty check` -> `pass`

## Notes

- `S02` `test_frontend_boundaries::test_installed_composition_and_native_journeys_are_runtime_owned` fails before and after this Step: it asserts a test file another session deleted
