---
tags:
  - '#exec'
  - '#attended-live-sign-in'
date: '2026-10-12'
modified: '2026-10-12'
body_schema: 'body-v2'
body_hash: 'sha256:81a4b18cf2fae28fd617fe91a89e0276b2d52315c1390e84975df36ca6f98d8e'
related:
  - "[[2026-10-12-attended-live-sign-in-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `attended-live-sign-in` ledger

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

- `S01` `A` `src/cadrumo/application/runtime/attendance.py`
- `S01` `M` `src/cadrumo/application/runtime/profile_access.py`
- `S01` `M` `src/cadrumo/application/user_profile/access_contracts.py`
- `S01` `M` `src/cadrumo/application/user_profile/session_authority_policy.py`
- `S01` `M` `src/cadrumo/application/user_profile/session_authority_core.py`
- `S01` `M` `src/cadrumo/application/user_profile/session_authority_access.py`
- `S01` `M` `src/cadrumo/application/user_profile/session_authority_admission.py`
- `S01` `A` `src/cadrumo/entrypoints/runtime/profile_connection_attendance.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/profile_connections.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/profile_connection_sessions.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/server_connection_handling.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/runtime_profile_transport.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/frontend_client.py`
- `S01` `A` `src/cadrumo/entrypoints/runtime/tests/test_attendance.py`
- `S01` `verify:` `pytest -m integration src/cadrumo/entrypoints/runtime/tests/test_attendance.py` -> `pass`
- `S01` `verify:` `mutation control (holder requirement disabled) fails test_attendance` -> `pass`
- `S01` `verify:` `pytest -m unit application/user_profile application/runtime custody/test_session_authority (1169)` -> `pass`
- `S01` `verify:` `pytest framing + session authority integration (100)` -> `pass`
- `S01` `verify:` `ruff check, ty check on changed modules` -> `pass`
- `S01` `by:` `claude`
- `S02` `A` `src/cadrumo/entrypoints/cli/config/sign_in_hold.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/_custody_command_specs.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/custody.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/custody_payloads.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/command_operation_table.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/command_frontend_counterparts.py`
- `S02` `M` `src/cadrumo_harness/_data/agent/reference/command-operations.md`
- `S02` `M` `src/cadrumo/locales/en/cli.yml`
- `S02` `M` `src/cadrumo/locales/es/cli.yml`
- `S02` `M` `src/cadrumo/locales/ca/cli.yml`
- `S02` `M` `src/cadrumo/locales/hu/cli.yml`
- `S02` `verify:` `aeat config sign-in-hold --help (dev env)` -> `pass`
- `S02` `verify:` `aeat config logout --help lists --secrets-stdin/--secrets-fd` -> `pass`
- `S02` `verify:` `pytest test_command_frontend_parity, test_command_operation_reference, test_command_operation_join (61)` -> `pass`
- `S02` `verify:` `ruff check, ty check on sign_in_hold.py and custody.py` -> `pass`
- `S02` `by:` `claude`
- `S03` `M` `src/cadrumo_harness/mcp/runtime_adapter.py`
- `S03` `M` `src/cadrumo_harness/mcp/runtime_admission.py`
- `S03` `M` `src/cadrumo_harness/mcp/tests/test_sign_in_resume.py`
- `S03` `verify:` `pytest src/cadrumo_harness/mcp/tests/test_sign_in_resume.py (27)` -> `pass`
- `S03` `verify:` `ruff check, ty check on runtime_adapter.py and runtime_admission.py` -> `pass`
- `S03` `by:` `claude`

## Notes

- `S02` Code was swept into c7fbea9454 by another session's catch-all commit; the counterpart declaration and regenerated reference landed in 9790b9e63c. Command name is config sign-in-hold (ADR hypothesis config sign-in hold); password arrives as the first stdin line, not --secrets-fd; both reconciled in the ADR under S04. Other CLI suites showed 11 failures from `runtime_deadline_exceeded/KDF_RESOURCE_LIMIT` under 100% host CPU from concurrent sessions, not from this change.
- `S03` Adapter code was swept into c7fbea9454 by another session; test updates committed in 9790b9e63c. Packaged end-to-end proof is S05.
