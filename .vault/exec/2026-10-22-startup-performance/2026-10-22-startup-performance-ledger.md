---
tags:
  - '#exec'
  - '#startup-performance'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:8ea72245744020461c9c8d77c299e0c221d477da98f56d24f8f77186e863fbc0'
related:
  - "[[2026-10-22-startup-performance-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `startup-performance` ledger

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

- `S01` `M` `dev/audit/registry_temporal_range_sweep.py`
- `S01` `M` `dev/registry/analysis/facts_catalogue_quality.py`
- `S01` `M` `dev/registry/binding_signal/sources.py`
- `S01` `M` `dev/registry/compiler/_validate_revision_sections.py`
- `S01` `M` `dev/registry/compiler/authority_database.py`
- `S01` `M` `dev/registry/compiler/convenio.py`
- `S01` `M` `dev/registry/compiler/loader.py`
- `S01` `M` `dev/registry/compiler/loader_materialisation.py`
- `S01` `M` `dev/registry/compiler/tests/test_bracket_coverage_support_floor.py`
- `S01` `M` `dev/registry/compiler/validate_below_floor_export_refs.py`
- `S01` `M` `dev/registry/compiler/validate_parameter_temporal.py`
- `S01` `M` `dev/registry/compiler/validate_revision_closure.py`
- `S01` `M` `dev/registry/eager_authority_baseline.py`
- `S01` `M` `dev/registry/edition_export_scenarios.py`
- `S01` `M` `dev/registry/pipeline/tests/_unpublished_modelo_registry.py`
- `S01` `M` `dev/registry/registry_collapse_authority_checks.py`
- `S01` `M` `dev/registry/registry_collapse_candidate.py`
- `S01` `M` `dev/registry/registry_collapse_requests.py`
- `S01` `M` `dev/registry/registry_collapse_run.py`
- `S01` `M` `dev/registry/supported_filing_years.py`
- `S01` `M` `dev/registry/tests/profile_schema_support.py`
- `S01` `M` `dev/registry/tests/test_authority.py`
- `S01` `M` `dev/registry/tests/test_convenio_facts.py`
- `S01` `M` `dev/registry/tests/test_deadline_window_ownership.py`
- `S01` `M` `dev/registry/tests/test_declared_inception_gate.py`
- `S01` `M` `dev/registry/tests/test_m347_threshold_buckets_authored.py`
- `S01` `M` `dev/registry/tests/test_modelo_200_editions_follow_their_own_designs.py`
- `S01` `M` `dev/registry/tests/test_modelo_220_editions_follow_their_own_designs.py`
- `S01` `M` `dev/registry/tests/test_registry_collapse_snapshot_stability.py`
- `S01` `M` `dev/registry/tests/test_registry_collapse_verification.py`
- `S01` `M` `dev/registry/tests/test_supported_filing_years_catalogue.py`
- `S01` `M` `dev/registry/tests/test_supported_filing_years_inception.py`
- `S01` `M` `dev/registry/tests/test_temporal.py`
- `S01` `M` `dev/registry/workbook_probe.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/authority_component_codec.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_resolution.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_string_mapping.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tax_identity_admission.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/temporal.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/authority_fakes.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/published_authority.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/registry_tree.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_validation_reads_the_facts_in_scope.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_declared_inception_runtime_gate.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_irnr_registry_tokens.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_irpf_income_category_order.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_iva_category_exclusions.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_iva_schema_vocabulary_projection_cache.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_iva_schema_vocabulary_required_legal_refs.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_m347_operation_scope.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_m347_threshold_buckets.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_pinned_authority_fact_resolution_cache.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_redaction_nif_iva.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_snapshot_continuity_source_windows.py`
- `S01` `M` `src/cadrumo/domain/transactions/tests/test_m210_retained_authority_scope.py`
- `S01` `M` `src/cadrumo/domain/transactions/tests/test_tipo_actividad_partitions.py`
- `S01` `A` `src/cadrumo/domain/calculations/registry/snapshot_globals.py`
- `S01` `verify:` `pytest test_redaction_nif_iva.py test_redaction_tax_identity_admission.py` -> `pass`
- `S01` `verify:` `pytest 28 files importing the moved types (379)` -> `pass`
- `S01` `verify:` `just check-types` -> `pass`
- `S01` `verify:` `lint-imports` -> `pass`
- `S02` `A` `src/cadrumo/adapters/persistence/storage/custody/change_witness.py`
- `S02` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/test_change_witness.py`
- `S02` `verify:` `pytest test_change_witness.py (17)` -> `pass`
- `S02` `verify:` `ruff, ty on touched files` -> `pass`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/automation_native_binding.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/automation_control_storage.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/custody/automation_store.py`
- `S03` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/test_custody_observation.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_host.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connections.py`
- `S03` `M` `src/cadrumo_runtime/host/profile_connection_admission.py`
- `S03` `A` `src/cadrumo_runtime/host/tests/test_login_observation.py`
- `S03` `verify:` `pytest runtime host and custody suites, all lanes (606 + new)` -> `pass`
- `S03` `verify:` `just check-types (one diagnostic in another session's uncommitted tui/app_navigation.py)` -> `pass`
- `S03` `verify:` `lint-imports 28 kept` -> `pass`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py`
- `S04` `M` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_profile_worker_custody_lease_window.py`
- `S04` `verify:` `pytest worker custody suites, all lanes` -> `pass`
- `S04` `verify:` `ruff, ty` -> `pass`
- `S05` `M` `.vault/audit/2026-10-22-startup-performance-request-path-audit.md`
- `S05` `verify:` `perf harness on overlaid package copy` -> `pass`
- `S11` `A` `src/cadrumo/application/workbench_generation_identity.py`
- `S11` `M` `src/cadrumo/application/workbench_generation_operation.py`
- `S11` `M` `src/cadrumo/application/tests/test_workbench_generation_operation.py`
- `S11` `M` `src/cadrumo_client/transport/workbench_generation.py`
- `S11` `M` `src/cadrumo_runtime/host/operation_authority.py`
- `S11` `M` `src/cadrumo_runtime/host/operation_host.py`
- `S11` `M` `src/cadrumo_runtime/host/tests/frontend/tui/entrypoints/tui/tests/test_runtime_workbench_native.py`
- `S11` `M` `src/cadrumo_runtime/host/tests/test_worker_startup_import_graph.py`
- `S11` `verify:` `pytest operation host/authority/workbench suites, all lanes (223)` -> `pass`
- `S11` `verify:` `import gate fails on the previous operation_authority` -> `pass`
- `S11` `verify:` `just check-types` -> `pass`
- `S11` `verify:` `lint-imports` -> `pass`
