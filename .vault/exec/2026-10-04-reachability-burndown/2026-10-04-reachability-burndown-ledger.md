---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:da5c051a9900e8ad5ba8d74cb50e24b606ee5f78da375f996f3b07141e26d8e0'
related:
  - "[[2026-10-04-reachability-burndown-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `reachability-burndown` ledger

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

- `S01` `M` `dev/audit/unreachable_frameworks.py`
- `S01` `M` `dev/audit/unreachable_definitions.py`
- `S01` `M` `dev/audit/tests/test_unreachable_frameworks.py`
- `S01` `verify:` `focused audit tests` -> `pass`
- `S01` `verify:` `focused Ruff and ty` -> `pass`
- `S02` `M` `src/cadrumo/core/atomic_write.py`
- `S02` `M` `src/cadrumo/core/locks.py`
- `S02` `M` `src/cadrumo/core/resources/bundled_data.py`
- `S02` `M` `src/cadrumo/core/observability/context.py`
- `S02` `M` `src/cadrumo/core/observability/capture.py`
- `S02` `A` `src/cadrumo/core/observability/tests/run_scope.py`
- `S02` `A` `src/cadrumo/core/observability/tests/envelope_capture.py`
- `S02` `A` `src/cadrumo/adapters/persistence/storage/master_key/tests/session_scope.py`
- `S02` `D` `src/cadrumo/core/tests/test_locks_async_acquisition.py`
- `S02` `D` `src/cadrumo/core/tests/test_observability_sink_inheritance.py`
- `S02` `verify:` `core and storage behavior tests (175)` -> `pass`
- `S02` `verify:` `focused Ruff format and ty` -> `pass`
- `S02` `verify:` `just check-types` -> `fail`
- `S02` `verify:` `just check-import-boundaries` -> `fail`
- `S02` `M` `src/cadrumo/adapters/outbound/llm/tests/test_evidence_consent_gate.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/master_key/active_session.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_active_session_thread_isolation.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_bucket_session_isolation.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/tests/test_diagnostics.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/tests/test_registration_leaves_the_profile_admitted.py`
- `S02` `M` `src/cadrumo/core/observability/tests/test_context_propagation.py`
- `S02` `M` `src/cadrumo/core/observability/tests/test_golden.py`
- `S02` `M` `src/cadrumo/core/observability/tests/test_logging_filter.py`
- `S02` `M` `src/cadrumo/core/observability/tests/test_models.py`
- `S02` `M` `src/cadrumo/core/tests/test_atomic_write.py`
- `S02` `M` `src/cadrumo/core/tests/test_resources.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_determinism_conformance.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_session_lifecycle_roundtrip.py`
- `S02` `M` `src/cadrumo/core/json_contract.py`
- `S02` `M` `src/cadrumo/core/observability/store.py`
- `S02` `M` `src/cadrumo/core/observability/sink.py`
- `S03` `M` `src/cadrumo/application/user_profile/profile_record_repository.py`
- `S03` `A` `src/cadrumo/application/user_profile/tests/record_session_scope.py`
- `S03` `M` `src/cadrumo/adapters/persistence/operations/tests/test_censal_operation_executor.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule_lifecycle.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_censal_reviewed_apply.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_complete_setup_schema_judgement.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_cotejo_apply_schema_judgement.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/tests/test_profile_health.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/tests/profile_capsule_runtime.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_registration.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/tests/test_active_profile_resolution.py`
- `S03` `M` `src/cadrumo/application/user_profile/tests/test_capsule_record_lineage_authority.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/_command_runtime.py`
- `S03` `A` `src/cadrumo/entrypoints/cli/tests/command_runtime_support.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_review_command_specs.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_app_quickfile_command_specs.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_app_live_command_specs.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_app_diagnostics_command_specs.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_command_runtime.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_overview_command_specs.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_work_command_specs.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_live_read_subgroups.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/errors.py`
- `S03` `A` `src/cadrumo/entrypoints/cli/tests/error_boundary_scope.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_active_profile_env_override_name.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_root_guard_typed_projection.py`
- `S03` `M` `src/cadrumo/application/modelo/work_wizard.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_work_wizard_flow.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_work_wizard.py`
- `S03` `verify:` `focused behavior tests (83 selected)` -> `pass`
- `S03` `verify:` `focused Ruff format and ty` -> `pass`
- `S03` `verify:` `integration lane (70 pass, 21 fail)` -> `fail`
- `S04` `M` `src/cadrumo/adapters/inbound/financial/providers/base.py`
- `S04` `M` `src/cadrumo/adapters/local_runtime/enrollment_client.py`
- `S04` `M` `src/cadrumo/application/bucket_maintenance/service.py`
- `S04` `M` `src/cadrumo/application/modelo/export.py`
- `S04` `M` `src/cadrumo/application/workflow/engine.py`
- `S04` `M` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
- `S04` `M` `src/cadrumo/domain/calculations/registry/queries.py`
- `S04` `M` `src/cadrumo/domain/contribuyente/descendant_guarderia.py`
- `S04` `M` `src/cadrumo/domain/filing/protocols.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/_ledger_m210_classify_cli.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/command_suggestions.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`
- `S04` `M` `src/cadrumo/domain/calculations/registry/censo_modelos.py`
- `S04` `M` `src/cadrumo/domain/calculations/registry/gasto193_bindings.py`
- `S04` `A` `src/cadrumo/domain/calculations/registry/tests/test_gasto193_observation.py`
- `S04` `D` `src/cadrumo/core/observability/fingerprint.py`
- `S04` `A` `src/cadrumo/core/observability/tests/fingerprint.py`
- `S04` `D` `src/cadrumo/core/observability/recorder.py`
- `S04` `A` `src/cadrumo/core/observability/tests/recorder.py`
- `S04` `D` `src/cadrumo/core/observability/sink.py`
- `S04` `A` `src/cadrumo/core/observability/tests/sink.py`
- `S04` `M` `dev/ci/tests/test_core_logging.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/tests/test_determinism_conformance.py`
- `S04` `M` `src/cadrumo/core/observability/tests/run_scope.py`
- `S04` `M` `src/cadrumo/core/observability/tests/test_fingerprint.py`
- `S04` `M` `src/cadrumo/core/observability/tests/test_logging_filter.py`
- `S04` `M` `src/cadrumo/core/observability/tests/test_sink.py`
- `S04` `M` `src/cadrumo/core/observability/tests/test_context_propagation.py`
- `S04` `M` `src/cadrumo/core/observability/tests/test_sink_redaction.py`
- `S04` `M` `src/cadrumo/core/tests/test_storage_fingerprint_participation_gate.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/profile_custody.py`
- `S04` `M` `src/cadrumo/application/user_profile/custody_ports.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/sede/_adapter_utils.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/sede/notifications.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/sede/censal_datos.py`
- `S04` `D` `src/cadrumo/adapters/outbound/aeat/sede/walker.py`
- `S04` `D` `src/cadrumo/adapters/outbound/aeat/sede/parse.py`
- `S04` `D` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_expand_matching_branches.py`
- `S04` `D` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_walker_remote_guard.py`
- `S04` `D` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_parse.py`
- `S04` `D` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_cotejo_csv_extraction.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/sede/schema.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_auth_state.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_walker_landing_refusal.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_pdf_response_contract.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_digest_field_parity.py`
- `S04` `M` `src/cadrumo/core/logging.py`
- `S04` `M` `src/cadrumo/core/observability/store.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations.py`
- `S04` `M` `src/cadrumo/application/live/justificante.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/tests/test_command_aeat_capability_probe.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/sede/_browser_constants.py`
- `S04` `M` `src/cadrumo/domain/user_profile/errors.py`
- `S04` `M` `src/cadrumo/adapters/inbound/financial/providers/csv.py`
- `S04` `M` `src/cadrumo/adapters/inbound/financial/providers/ofx.py`
- `S04` `M` `src/cadrumo/adapters/inbound/financial/providers/pdf_n26.py`
- `S04` `M` `src/cadrumo/adapters/inbound/financial/providers/xls.py`
- `S04` `M` `src/cadrumo/adapters/inbound/financial/providers/xlsx.py`
- `S04` `M` `src/cadrumo/adapters/inbound/financial/providers/_mapped_tabular.py`
- `S04` `M` `src/cadrumo/adapters/inbound/financial/providers/_constants.py`
- `S04` `A` `dev/audit/unreachable_schemas.py`
- `S04` `A` `dev/audit/unreachable_schema_consumers.py`
- `S04` `A` `dev/audit/unreachable_members.py`
- `S04` `M` `dev/audit/unreachable_findings.py`
- `S04` `M` `dev/audit/unreachable_graph.py`
- `S04` `M` `dev/audit/unreachable_references.py`
- `S04` `A` `dev/audit/tests/test_unreachable_schemas.py`
- `S04` `A` `dev/audit/tests/test_unreachable_members.py`
- `S04` `M` `.codex/rules/14-tax-calculation-domain.md`
- `S04` `M` `.agents/skills/cadrumo-start/references/14-tax-calculation-domain.md`
- `S04` `M` `dev/quality/metadata/import_load_targets.json`
- `S04` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S04` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S04` `verify:` `focused audit tests (69 passed)` -> `pass`
- `S04` `verify:` `observability and determinism tests (124 passed)` -> `pass`
- `S04` `verify:` `browser, landing and PDF contracts (152 passed)` -> `pass`
- `S04` `verify:` `financial providers and profile custody (161 passed)` -> `pass`
- `S04` `verify:` `expense, provenance and CLI capability tests (21 passed)` -> `pass`
- `S04` `verify:` `owned source Ruff check and format` -> `pass`
- `S04` `verify:` `owned source and scanner ty check` -> `pass`
- `S04` `verify:` `broader sede unit run (708 passed, 33 failures)` -> `fail`

## Notes

- `S01` Fresh scan 285 candidates across 3217 modules; candidate count is a live observation. Assigned validators and Click dispatch resolved without identity exemptions.
- `S02` Type errors are in concurrent reconciliation test changes. Import checks loaded every attempted module with no broken contracts but source and census changed during execution; final stable verification remains S07.
- `S03` 91 integration/platform cases remain for S07. Removed test-only convenience doors and updated test consumers; real operator implementations unchanged.
- `S03` 21 integration failures require an unavailable runtime endpoint or Windows Credential Manager synthetic probe. Native credential error 1312 reports no logon session; no persistent-service bridge or security bypass is authorized. Host-dependent verification remains pending S07.
- `S04` The broader adapter failures include missing Chromium under isolated test roots and concurrent filing-layout changes. Pinning the provisioned component directory makes all 152 affected focused browser contracts pass. Final tree import/type checks and remaining findings stay open in S07 and S08.
