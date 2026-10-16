---
tags:
  - '#exec'
  - '#idle-churn'
date: '2026-10-16'
modified: '2026-10-16'
body_schema: 'body-v2'
body_hash: 'sha256:f2bf775034677b4d251d994caa4e7e26d47f0376241e420be3be3366573384b2'
related:
  - "[[2026-10-16-idle-churn-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `idle-churn` ledger

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

- `S01` `M` `src/cadrumo_client/contracts/service_access.py`
- `S01` `M` `src/cadrumo/core/path_confinement.py`
- `S01` `M` `src/cadrumo_runtime/adapters/service_verification.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_connection_extension_records.py`
- `S01` `M` `src/cadrumo_runtime/host/profile_connection_services.py`
- `S01` `M` `src/cadrumo_runtime/host/tests/test_service_records.py`
- `S01` `A` `src/cadrumo_runtime/adapters/tests/test_service_verification.py`
- `S01` `verify:` `pytest -n0 -m '' test_service_verification.py test_service_records.py` -> `pass`
- `S01` `verify:` `ruff check + ruff format --check + ty check on touched files` -> `pass`
- `S02` `M` `src/cadrumo_runtime/host/worker_service.py`
- `S02` `M` `src/cadrumo_runtime/host/worker_operation_requests.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py`
- `S02` `M` `src/cadrumo_runtime/host/profile_login.py`
- `S02` `M` `src/cadrumo_runtime/host/worker_submission_staging.py`
- `S02` `M` `src/cadrumo_runtime/host/tests/test_worker_exit_cleanup.py`
- `S02` `M` `src/cadrumo_runtime/host/tests/test_worker_submission_staging.py`
- `S02` `M` `src/cadrumo_runtime/host/tests/test_human_login_receipt.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_profile_worker_custody_lease_window.py`
- `S02` `verify:` `pytest -n0 worker exit cleanup, submission staging, custody lease window` -> `pass`
- `S02` `verify:` `pytest -n0 test_human_login_receipt.py` -> `fail`
- `S02` `verify:` `ruff check, ruff format --check, ty check on touched files` -> `pass`
- `S03` `M` `src/cadrumo_client/contracts/session_events.py`
- `S03` `M` `src/cadrumo_client/contracts/sign_in.py`
- `S03` `M` `src/cadrumo_client/transport/verified_transport.py`
- `S03` `M` `src/cadrumo_client/transport/frontend_client.py`
- `S03` `M` `src/cadrumo_runtime/host/session_events.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connections.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connection_sessions.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connection_services.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connection_attendance.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connection_operations.py`
- `S03` `M` `src/cadrumo_runtime/host/tests/test_profile_language_events.py`
- `S03` `A` `src/cadrumo_runtime/host/tests/test_connection_cues.py`
- `S03` `A` `src/cadrumo_runtime/host/tests/test_sign_in_watch.py`
- `S03` `A` `src/cadrumo_client/transport/tests/test_invalidation_cues.py`
- `S03` `verify:` `pytest -n0 connection cues, sign-in watch, attendance, lifecycle notices, session events, sign-in status, service records, client cue and language tests` -> `pass`
- `S03` `verify:` `ruff check, ruff format --check, ty check on touched files` -> `pass`
- `S04` `M` `src/cadrumo_agent_service/main.py`
- `S04` `M` `src/cadrumo_agent_service/service.py`
- `S04` `M` `src/cadrumo_agent_service/providers/persistence/store.py`
- `S04` `M` `src/cadrumo_client/transport/service_client.py`
- `S04` `M` `src/cadrumo_agent_service/host/tests/test_service_stdin_lifetime.py`
- `S04` `A` `src/cadrumo_agent_service/providers/persistence/tests/test_store_generations.py`
- `S04` `verify:` `pytest -n0 service stdin lifetime, store generations, hosted certification, admin authority` -> `pass`
- `S04` `verify:` `ruff check, ruff format --check, ty check on touched files` -> `pass`

## Notes

- `S01` `profile_connection_services.py` interleaves with another session's uncommitted lease-guard and refusal-check hunks; its claim and admission recheck stays uncommitted until those land, while HEAD's full verification there still works with the new verifier.
- `S02` `test_worker_human_login_receipt_lifecycle[success]` fails on CADRUMO-RUNTIME-DEBUG's uncommitted `_ended` change in `profile_worker_custody.retire` (retired sessions now refuse with `authentication_required);` the other seven modes pass and the failure was reported to that session.
- `S03` Four files carry other sessions' uncommitted hunks; this Step's edits were staged as a HEAD-relative patch with git apply --cached, leaving theirs in the working tree. The S01 claim and admission recheck rides in the same patch.
- `S04` AgentDiagnosticFiles still tails the hosted agent's log files every 0.2 s while an agent runs; directory change notifications fire only when a writer closes its handle (measured: at exit), so moving it to them needs a decision on worker diagnostics with the cadrumo-agent owner.
