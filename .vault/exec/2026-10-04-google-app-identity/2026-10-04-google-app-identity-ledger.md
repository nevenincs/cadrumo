---
tags:
  - '#exec'
  - '#google-app-identity'
date: '2026-10-04'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:782c2d90e6a68a4453e46841ad86a1c73444dd3fbe4b4ccce3e95cbf3aca8592'
related:
  - "[[2026-10-04-google-app-identity-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `google-app-identity` ledger

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

- `S01` `D` `src/cadrumo/core/google_credential_source.py`
- `S01` `D` `src/cadrumo/adapters/outbound/google/impersonation.py`
- `S01` `D` `src/cadrumo/adapters/outbound/google/tests/test_impersonation.py`
- `S01` `D` `src/cadrumo/adapters/outbound/google/tests/test_impersonation_live.py`
- `S01` `D` `src/cadrumo/entrypoints/cli/config/_google_credential_source_cli.py`
- `S01` `D` `src/cadrumo/entrypoints/cli/config/_google_credential_source_payloads.py`
- `S01` `D` `src/cadrumo/entrypoints/cli/config/tests/test_google_credential_source_cli.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/errors.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/google_configuration_inputs.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/google_configuration_refusal.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/records.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/session_store.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/tests/test_auth_preconditions.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/tests/test_session_store_namespace_binding.py`
- `S01` `M` `src/cadrumo/adapters/outbound/google/tests/test_session_store_roundtrip.py`
- `S01` `M` `src/cadrumo/adapters/outbound/storage/factory.py`
- `S01` `M` `src/cadrumo/adapters/outbound/storage/tests/test_factory.py`
- `S01` `M` `src/cadrumo/adapters/outbound/storage/tests/test_google_configuration_admission.py`
- `S01` `M` `src/cadrumo/adapters/outbound/storage/tests/test_validation_preconditions.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `S01` `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `S01` `M` `src/cadrumo/application/user_profile/google_configuration_operation_contracts.py`
- `S01` `M` `src/cadrumo/application/user_profile/google_configuration_operation_refusal.py`
- `S01` `M` `src/cadrumo/application/user_profile/tests/test_google_configuration_operation.py`
- `S01` `M` `src/cadrumo/core/errors/registry/_adapters_part2.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/_profile_authentication_gate.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/_google_command_specs.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/google.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/google_configuration_contract_map.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/google_configuration_receipt_correlation.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/google_configuration_source_correlation.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/test_google_command_specs.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_google_configuration_native.py`
- `S01` `M` `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`
- `S01` `M` `src/cadrumo/entrypoints/google_configuration_operation_composition.py`
- `S01` `M` `src/cadrumo/entrypoints/tests/conformance_google_support.py`
- `S01` `M` `src/cadrumo/entrypoints/tests/test_google_configuration_operation_composition.py`
- `S01` `M` `src/cadrumo/locales/ca/cli.yml`
- `S01` `M` `src/cadrumo/locales/en/cli.yml`
- `S01` `M` `src/cadrumo/locales/es/cli.yml`
- `S01` `M` `src/cadrumo/locales/hu/cli.yml`
- `S01` `M` `src/cadrumo/locales/ca/errors.yml`
- `S01` `M` `src/cadrumo/locales/en/errors.yml`
- `S01` `M` `src/cadrumo/locales/es/errors.yml`
- `S01` `M` `src/cadrumo/locales/hu/errors.yml`
- `S01` `M` `dev/locales/fstring_registry.py`
- `S01` `M` `dev/quality/metadata/application_entrypoint_modules.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S01` `M` `dev/quality/metadata/import_load_targets.json`
- `S01` `verify:` `pytest unit: google adapter, storage factory, namespace registry, error registry, CLI specs (87 tests)` -> `pass`
- `S01` `verify:` `pytest integration: google configuration composition, operation contracts, registered-executor conformance for config.google (34 tests)` -> `pass`
- `S01` `verify:` `pytest integration windows_only: native google configuration CLI journey` -> `pass`
- `S01` `verify:` `ruff check and ruff format --check on touched files` -> `pass`
- `S01` `verify:` `just check-types` -> `fail`
- `S01` `verify:` `just check-import-boundaries` -> `fail`
- `S01` `verify:` `dev.locales status --json --check` -> `fail`
- `S01` `by:` `CADRUMO-GOOGLE-OATH`

## Notes

- `S01` check-types reports 3 ty diagnostics, all in dev/packaging/native files this Step does not touch; none in files changed here.
- `S01` check-import-boundaries kept all 15 contracts with zero hard findings, but its verdict is unavailable: the shared `import_load_targets` metadata is stale against other sessions' uncommitted modules, and the source tree changed while the gate ran.
- `S01` The locale status check fails on a standing backlog (catalogue-only keys, spelling review); it reports no missing, unrepaired or invalid cell and requires none of the keys removed here.
- `S01` Shared generated files carry other sessions' uncommitted changes; only this Step's lines are committed in the four errors.yml catalogues and the two `import_load_targets` files.
- `S01` docs/technical articles and their translations still describe the removed source; they are rewritten in S09.
