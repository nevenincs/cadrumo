---
tags:
  - '#exec'
  - '#google-app-identity'
date: '2026-10-04'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:1959b7d68d0437b48797024636a54b500cb0fba1a39613eab61706925b7b8eb9'
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
- `S02` `D` `src/cadrumo/adapters/outbound/google/document_acquisition.py`
- `S02` `D` `src/cadrumo/adapters/outbound/google/document_link_resolver.py`
- `S02` `D` `src/cadrumo/application/ledger/evidence_sweep.py`
- `S02` `D` `src/cadrumo/application/ledger/evidence_sweep_ports.py`
- `S02` `D` `src/cadrumo/adapters/outbound/google/tests/test_document_acquisition_admission.py`
- `S02` `D` `src/cadrumo/adapters/outbound/google/tests/test_document_link_resolve_roundtrip.py`
- `S02` `D` `src/cadrumo/adapters/outbound/google/tests/test_document_link_resolver.py`
- `S02` `D` `src/cadrumo/adapters/outbound/google/tests/test_drive_folder_bulk_fetch_roundtrip.py`
- `S02` `D` `src/cadrumo/adapters/outbound/google/tests/test_drive_folder_listing.py`
- `S02` `D` `src/cadrumo/application/ledger/tests/test_evidence_sweep.py`
- `S02` `D` `src/cadrumo/entrypoints/cli/tests/test_drive_folder_reference.py`
- `S02` `D` `docs/_sequences/contracts/how-to/import-bank-statements/import-evidence-pull.seq`
- `S02` `D` `docs/_sequences/contracts/how-to/ledger-evidence/ledger-evidence-pull-all.seq`
- `S02` `D` `docs/_sequences/contracts/how-to/ledger-evidence/ledger-evidence-pull.seq`
- `S02` `M` `dev/audit/vulture_whitelist.py`
- `S02` `M` `dev/docs/sequences/schema.py`
- `S02` `M` `dev/docs/tests/test_static_frame_reasons.py`
- `S02` `M` `dev/quality/metadata/application_entrypoint_modules.json`
- `S02` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S02` `M` `dev/quality/metadata/import_load_targets.json`
- `S02` `M` `docs/how-to/import-bank-statements.md`
- `S02` `M` `docs/how-to/ledger-evidence.md`
- `S02` `M` `src/cadrumo/adapters/outbound/storage/tests/test_google_drive.py`
- `S02` `M` `src/cadrumo/adapters/outbound/storage/tests/test_google_drive_failure_preconditions.py`
- `S02` `M` `src/cadrumo/application/ledger/evidence.py`
- `S02` `M` `src/cadrumo/application/ledger/evidence_ingestion_contracts.py`
- `S02` `M` `src/cadrumo/application/ledger/evidence_ingestion_operation.py`
- `S02` `M` `src/cadrumo/application/ledger/evidence_ingestion_operation_ports.py`
- `S02` `M` `src/cadrumo/application/ledger/tests/evidence_ingestion_operation_support.py`
- `S02` `M` `src/cadrumo/application/ledger/tests/test_evidence_ingestion_operation.py`
- `S02` `M` `src/cadrumo/core/errors/registry/_application_part3a2.py`
- `S02` `M` `src/cadrumo/core/google_drive_reference.py`
- `S02` `M` `src/cadrumo/core/tests/test_google_drive_reference.py`
- `S02` `M` `src/cadrumo/domain/attachments/enums.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_app_ledger_command_spec_policies.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_app_ledger_management_command_specs.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_app_ledger_operations_command_specs.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_ledger.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_profile_authentication_gate.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/runtime_ledger_evidence_ingestion.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_app_ledger_operations_management_command_specs.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_ledger_notice_action_conformance.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_local_path_spelling.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_runtime_ledger_evidence_ingestion_native.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_transport_locus_declared.py`
- `S02` `M` `src/cadrumo/entrypoints/ledger_evidence_ingestion_operation_composition.py`
- `S02` `M` `src/cadrumo/entrypoints/tests/conformance_ledger_evidence_ingestion_support.py`
- `S02` `M` `src/cadrumo/entrypoints/tests/conformance_ledger_seed_support.py`
- `S02` `M` `src/cadrumo/locales/ca/cli.yml`
- `S02` `M` `src/cadrumo/locales/en/cli.yml`
- `S02` `M` `src/cadrumo/locales/es/cli.yml`
- `S02` `M` `src/cadrumo/locales/hu/cli.yml`
- `S02` `M` `src/cadrumo/locales/ca/errors.yml`
- `S02` `M` `src/cadrumo/locales/en/errors.yml`
- `S02` `M` `src/cadrumo/locales/es/errors.yml`
- `S02` `M` `src/cadrumo/locales/hu/errors.yml`
- `S02` `R` `src/cadrumo/adapters/outbound/google/tests/drive_media_server.py` -> `src/cadrumo/adapters/outbound/google/tests/drive_list_server.py`
- `S02` `verify:` `pytest unit: evidence ingestion, Drive reference, Drive provider, attachments, CLI ledger specs and conformance gates (438 tests)` -> `pass`
- `S02` `verify:` `pytest unit: CLI, CLI config, operator surface, ledger and entrypoints suites (5219 tests)` -> `pass`
- `S02` `verify:` `pytest integration: registered-executor conformance for ledger evidence (18 tests)` -> `pass`
- `S02` `verify:` `pytest integration windows_only: native evidence batch journey` -> `pass`
- `S02` `verify:` `pytest docs lane: sequence contract, directive and static-frame tests (38 tests)` -> `pass`
- `S02` `verify:` `ruff check and ruff format --check on touched files` -> `pass`
- `S02` `verify:` `just check-types` -> `fail`
- `S02` `verify:` `just check-import-boundaries` -> `fail`
- `S02` `verify:` `dev.docs.sequences check --page how-to/ledger-evidence` -> `fail`
- `S02` `by:` `CADRUMO-GOOGLE-OATH`
- `S03` `M` `src/cadrumo/core/external_constants.toml`
- `S03` `M` `src/cadrumo/core/external_constants.py`
- `S03` `M` `src/cadrumo/adapters/outbound/google/records.py`
- `S03` `M` `src/cadrumo/adapters/outbound/google/calc_sheets_apply.py`
- `S03` `M` `src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`
- `S03` `M` `src/cadrumo/adapters/outbound/google/tests/test_records.py`
- `S03` `M` `src/cadrumo/adapters/outbound/google/tests/test_oauth_flow.py`
- `S03` `M` `src/cadrumo/adapters/outbound/storage/tests/test_factory.py`
- `S03` `M` `stubs/google_auth_oauthlib/flow.pyi`
- `S03` `verify:` `pytest unit: scope set, consent URL scopes through the real installed-app flow, hydrated credential scopes, records and factory (57 tests)` -> `pass`
- `S03` `verify:` `pytest unit and integration: Google adapters, storage, calc sheets, export and CLI config outside the conformance suite (541 tests)` -> `pass`
- `S03` `verify:` `git grep for the spreadsheets, drive.readonly and gmail.readonly scope strings in non-test source` -> `pass`
- `S03` `verify:` `ruff check, ruff format --check and ty on touched files` -> `pass`
- `S03` `verify:` `pytest integration: registered-executor conformance` -> `fail`
- `S03` `verify:` `just check-types` -> `fail`
- `S03` `verify:` `just check-import-boundaries` -> `fail`
- `S03` `by:` `CADRUMO-GOOGLE-OATH`

## Notes

- `S01` check-types reports 3 ty diagnostics, all in dev/packaging/native files this Step does not touch; none in files changed here.
- `S01` check-import-boundaries kept all 15 contracts with zero hard findings, but its verdict is unavailable: the shared `import_load_targets` metadata is stale against other sessions' uncommitted modules, and the source tree changed while the gate ran.
- `S01` The locale status check fails on a standing backlog (catalogue-only keys, spelling review); it reports no missing, unrepaired or invalid cell and requires none of the keys removed here.
- `S01` Shared generated files carry other sessions' uncommitted changes; only this Step's lines are committed in the four errors.yml catalogues and the two `import_load_targets` files.
- `S01` docs/technical articles and their translations still describe the removed source; they are rewritten in S09.
- `S02` check-types reports 14 diagnostics in files this Step does not touch (invoice catalogue tests, modelo workbench operations, typed financial operands); none in files changed here.
- `S02` check-import-boundaries kept all 15 contracts; its two hard findings name `cadrumo.application.modelo.workbench_operations,` a module another session is moving, and the shared import inventory is stale against their uncommitted work.
- `S02` The documentation sequence check refused to execute any frame because the published registry authority is stale against other sessions' legal-source changes; the removed sequence contracts were checked by the docs-lane structure tests instead.
- `S02` Two unit failures seen in broad runs belong elsewhere: an unregistered SupervisorLineError in the runtime supervisor work, and one profile-guard recovery test that passes when run alone. The native evidence journey also failed twice while a 12-minute suite shared the machine and passes alone.
- `S02` Observation, not changed here: when a batch custody write is uncertain, the batch projection rejects the UNKNOWN effect with a pydantic ValidationError instead of the designed refusal; the terminal effect is still reported UNKNOWN.
- `S02` The AttachmentSource members GMAIL, `GOOGLE_DRIVE` and URL and `AttachmentKind.DRIVE_DOCUMENT` are kept as stored-history vocabulary; only the DocumentLinkSource CLI choice is removed.
- `S02` Translated documentation catalogues under docs/locales still carry the removed how-to passages; they are refreshed with S09.
- `S02` Shared files carry other sessions' uncommitted changes; only this Step's lines are committed in evidence.py, `_ledger.py,` `ledger_lifecycle_cli.py,` `_application_part3a2.py,` the four errors.yml catalogues and the two `import_load_targets` files.
- `S03` The scope change is pending verification: no live run under drive.file alone has exercised the Sheets and Drive methods the export calls. That proof is S10 and is not claimed here.
- `S03` The registered-executor conformance suite cannot start in the shared tree: the operation supervisor another session is editing refuses with 'typed financial operations require hardened durable custody' for every scenario, including non-Google ones. It passed for the Google and evidence families before that edit appeared.
- `S03` check-types reports diagnostics only in files this Step does not touch after the two new tests were made type-clean; the local InstalledAppFlow stub gained the two members the consent-URL test calls.
- `S03` check-import-boundaries kept all 15 contracts; its two hard findings are in modelo workbench tests another session is changing.
- `S03` One native automation-change test failed in a broad run; it does not involve Google scopes.
