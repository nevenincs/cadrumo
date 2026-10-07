---
tags:
  - '#exec'
  - '#dead-code-zero'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:8e85bc3ff82a9c0ee1ec82bb7200f377c7c4819680625dad41bc6f8c9219277c'
related:
  - "[[2026-10-07-dead-code-zero-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `dead-code-zero` ledger

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

- `S01` `M` `src/cadrumo/application/user_profile/custody_ports.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/profile_custody.py`
- `S01` `M` `src/cadrumo/application/user_profile/login_session_port.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/profile_login_session.py`
- `S01` `M` `src/cadrumo/application/user_profile/profile_pointer.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/profile_connections.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/calc_sheets_apply.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/errors.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/root_folder.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/managed_artifacts.py`
- `S01` `M` `src/cadrumo/core/transport_locus.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/tests/test_profile_custody_adapter.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/tests/test_profile_login_session_adapter.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/tests/test_cli_commands_leave_no_unsealed_bucket_session.py`
- `S01` `M` `src/cadrumo/application/user_profile/tests/test_pointer_transition_authority.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_custody_transactions.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_bootstrap_delete.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/tests/test_supervised_channel.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/tests/test_managed_artifacts.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/tests/test_transport_locus_declared.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/tests/test_app_ledger_operations_management_command_specs.py`
- `S01` `D` `src/cadrumo/adapters/persistence/storage/tests/local_record_probe.py`
- `S01` `verify:` `focused owning tests with hosted and corrected CLI cases rerun: 88 passed, 2 OS-keychain skips` -> `pass`
- `S01` `verify:` `scoped Ruff lint and format` -> `pass`
- `S01` `verify:` `scoped ty check all S01 paths` -> `pass`
- `S02` `M` `dev/audit/unreachable_code.py`
- `S02` `M` `dev/audit/unreachable_findings.py`
- `S02` `M` `dev/audit/unreachable_frameworks.py`
- `S02` `M` `dev/audit/unreachable_members.py`
- `S02` `M` `dev/audit/unreachable_outside.py`
- `S02` `A` `dev/audit/unreachable_records.py`
- `S02` `M` `dev/audit/tests/test_unreachable_members.py`
- `S02` `M` `dev/audit/tests/test_unreachable_frameworks.py`
- `S02` `A` `dev/audit/tests/test_unreachable_records.py`
- `S02` `M` `src/cadrumo/core/diagnostic_log.py`
- `S02` `M` `src/cadrumo/core/tests/test_diagnostic_log.py`
- `S02` `verify:` `focused analyzer, formatter, rotation and audit tests: 156 distinct passing cases after corrective rerun` -> `pass`
- `S02` `verify:` `scoped Ruff lint and format` -> `pass`
- `S02` `verify:` `scoped ty check all S02 paths` -> `pass`
- `S02` `verify:` `Vulture JSON: zero findings across 3265 offered modules` -> `pass`

## Notes

- `S01` Full configured types initially reported 11 diagnostics in concurrent registry/native packaging work outside S01; scoped S01 check is clean. Initial hosted timeout passed serially. Retired frontend receipt-resume test seam replaced with real runtime and explicit credentials.
- `S02` Second reachability pass exposed three schema fields after a concurrent registry refactor. S03 will resolve that structural coverage and re-measure the complete tree.
