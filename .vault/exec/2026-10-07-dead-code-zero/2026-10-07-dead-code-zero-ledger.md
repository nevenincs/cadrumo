---
tags:
  - '#exec'
  - '#dead-code-zero'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:f0ee7c3cd72c9d99aa587296b61d230632c915b8a7df7aa7d6941d27b9b56570'
related:
  - "[[2026-10-07-dead-code-zero-plan]]"
---

# `dead-code-zero` ledger

## Changes

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
- `S03` `M` `dev/audit/unreachable_code.py`
- `S03` `M` `dev/audit/unreachable_models.py`
- `S03` `M` `dev/audit/unreachable_records.py`
- `S03` `M` `dev/audit/unreachable_schema_consumers.py`
- `S03` `A` `dev/audit/unreachable_schema_validators.py`
- `S03` `M` `dev/audit/tests/test_unreachable_records.py`
- `S03` `M` `dev/audit/tests/test_unreachable_schemas.py`
- `S03` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S03` `M` `dev/quality/metadata/import_load_targets.json`
- `S03` `M` `src/cadrumo/application/operations/registry.py`
- `S03` `M` `.vault/audit/2026-10-07-dead-code-zero-tooling-coverage-audit.md`
- `S03` `M` `.vault/plan/2026-10-07-dead-code-zero-plan.md`
- `S03` `M` `.vault/index/dead-code-zero.index.md`
- `S03` `verify:` `full typed reachability scan and configured module-symbol-export predicates: zero populations` -> `pass`
- `S03` `verify:` `native audit-dead-weight: zero Vulture findings across 3265 offered modules` -> `pass`
- `S03` `verify:` `all twelve configured quality gates with final corrections and stable snapshot evidence` -> `pass`
- `S03` `verify:` `focused stable snapshot pytest unit and integration: 104 cases` -> `pass`
- `S03` `verify:` `focused census extension: 73 distinct cases after corrective rerun` -> `pass`
- `S03` `verify:` `final scoped Ruff lint-format and ty` -> `pass`
- `S03` `verify:` `integrated S01-S03 review recorded in rolling audit` -> `pass`

## Notes

- `S01` Full configured types initially reported 11 diagnostics in concurrent registry/native packaging work outside S01; scoped S01 check is clean. Initial hosted timeout passed serially. Retired frontend receipt-resume test seam replaced with real runtime and explicit credentials.
- `S02` Second reachability pass exposed three schema fields after a concurrent registry refactor. S03 will resolve that structural coverage and re-measure the complete tree.
- `S03` Concurrent shared-tree edits invalidated import authority snapshots. The unchanged configured gates pass against baseline f0be8532f5 plus the exact owned patch; all ten owned file hashes match. Source state and evidence details are in the rolling audit.
