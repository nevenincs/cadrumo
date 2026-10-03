---
tags:
  - '#exec'
  - '#binding-consumer-closure'
date: '2026-10-02'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:9989d3f5fa198421a56f4be6cfc844487c677668d48b4ef8adb33e9adbb547c3'
related:
  - "[[2026-10-02-binding-consumer-closure-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `binding-consumer-closure` ledger

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

- `S01` `M` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/bindings/0001-declarations.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/form_layouts/0001-form-layout.toml`
- `S01` `M` `dev/registry/mappings/modelo_360/2010/0002-pagina01.toml`
- `S01` `M` `dev/registry/mappings/modelo_360/2010/0003-pagina02.toml`
- `S01` `M` `src/cadrumo/application/modelo/work_form.py`
- `S01` `M` `src/cadrumo/application/modelo/tests/test_work_form_binding_labels.py`
- `S01` `R` `src/cadrumo/entrypoints/tests/test_modelo_wire_input_alias.py` -> `src/cadrumo/entrypoints/tests/test_modelo_casilla_wire_slot.py`
- `S01` `verify:` `python -m dev.registry.conformance valid` -> `pass`
- `S01` `verify:` `python -m dev.registry.form_layout generate --modelo 360 --check` -> `pass`
- `S01` `verify:` `pytest test_work_form_binding_labels test_work_form_grids test_modelo_casilla_wire_slot test_row_bindings_are_consumed -m 'unit or integration' (23)` -> `pass`
- `S01` `verify:` `basedpyright, ty, pyrefly on changed modules` -> `pass`
- `S02` `A` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2026/identifier_evolutions/0001-declarations.toml`
- `S02` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2026/form_layouts/0001-form-layout.toml`
- `S02` `verify:` `python -m dev.registry.conformance valid` -> `pass`
- `S03` `D` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2022/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2022/constructs/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2022/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2022/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/revision.toml`
- `S03` `D` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/constructs/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/constructs/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-desde-09-y-3t/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-hasta-08-y-2t/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-hasta-08-y-2t/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-hasta-08-y-2t/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/constructs/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/form_layouts/0001-form-layout.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/bindings/0001-declarations.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/revision.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/revision.toml`
- `S03` `A` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-desde-09-y-3t/bindings/`
- `S03` `A` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/`
- `S03` `M` `dev/registry/tests/test_modelo_184_filing_surface_across_supported_years.py`
- `S03` `M` `dev/registry/tests/test_modelo_390_registry.py`
- `S03` `M` `dev/registry/tests/test_ledger_iva_aggregation_binding_exports_recargo.py`
- `S03` `M` `src/cadrumo/adapters/persistence/profile/tests/test_modelo_303_compensacion_carry_forward_continuity.py`
- `S03` `M` `dev/registry/form_layout/tests/test_form_layout_integrity.py`
- `S03` `verify:` `typed equivalence (scratch loader diff) 232/184/390/303: only intended losses plus source_refs corrected to each edition's own design` -> `pass`
- `S03` `verify:` `python -m dev.registry.conformance valid` -> `pass`
- `S03` `verify:` `affected registry, calculation and persistence tests (421)` -> `pass`
- `S04` `M` `src/cadrumo/domain/calculations/registry/schema_surfaces.py`
- `S04` `M` `src/cadrumo/domain/calculations/registry/tests/test_schema.py`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/revision.toml`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/bindings/0001-declarations.toml`
- `S04` `verify:` `pytest test_schema -k 'not_bound or input_kind'` -> `pass`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/bindings/0001-declarations.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/revision.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/form_layouts/0001-form-layout.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/form_layouts/0001-form-layout.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/casilla_continuidad_evolutions/0001-declarations.toml`
- `S07` `D` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/casilla_continuidad_evolutions/0002-p05-s50-0309-0316.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2019-2022/bindings/0001-declarations.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0001-declarations.toml`
- `S07` `verify:` `python -m dev.registry.edition_delta_migration --modelo 200/202/130 (non-applying): changed=False, equivalence passed, minimality passed` -> `pass`
- `S07` `verify:` `python -m dev.registry.form_layout generate --modelo 200 202 720 130 --check` -> `pass`
- `S07` `verify:` `pytest test_committed_authored_sections_are_consolidated test_delta_minimality test_bindings_* -m 'unit or integration'` -> `pass`
- `S06` `M` `src/cadrumo/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/bindings/0001-declarations.toml`
- `S06` `verify:` `python -m dev.registry.edition_delta_migration --modelo 720 (non-applying): changed=False, equivalence passed` -> `pass`
- `S06` `verify:` `pytest test_modelo_720_prior_year_baseline_fidelity test_modelo_720_redeclaration_e2e -m 'unit or integration'` -> `pass`
- `S10` `M` `dev/quality/metadata/import_load_targets.json`
- `S10` `M` `dev/registry/bindings.py`
- `S10` `M` `dev/registry/tests/test_binding_build_validation.py`
- `S10` `A` `dev/registry/tests/test_bindings_unconsumed_filing_grade.py`
- `S10` `M` `dev/registry/tests/test_detail_record_modelo_coverage.py`
- `S10` `M` `dev/registry/tests/test_validate_bindings.py`
- `S10` `M` `justfile`
- `S10` `D` `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2022-2023/bindings/0001-declarations.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2022-2023/constructs/0001-declarations.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2022-2023/form_layouts/0001-form-layout.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2024/form_layouts/0001-form-layout.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2024/revision.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2025/form_layouts/0001-form-layout.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2025/revision.toml`
- `S10` `R` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/bindings/0001-declarations.toml` -> `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/bindings/0001-declarations.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/constructs/0001-declarations.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/form_layouts/0001-form-layout.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/revision.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/form_layouts/0001-form-layout.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/revision.toml`
- `S10` `D` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/bindings/0001-declarations.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/constructs/0001-declarations.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/form_layouts/0001-form-layout.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/revision.toml`
- `S10` `M` `src/cadrumo/application/calculations/row_set_assembly.py`
- `S10` `M` `src/cadrumo/application/calculations/tests/test_grouping_dispatch_coverage.py`
- `S10` `M` `src/cadrumo/application/calculations/tests/test_row_set_assembly.py`
- `S10` `M` `src/cadrumo/application/modelo/source_policy.py`
- `S10` `M` `src/cadrumo/application/modelo/tests/test_source_mesh_missing_sources.py`
- `S10` `M` `src/cadrumo/application/state_projection.py`
- `S10` `M` `src/cadrumo/core/aggregation.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/binding_provider.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/detail_record_bindings.py`
- `S10` `D` `src/cadrumo/domain/calculations/registry/donativo_bindings.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_aggregation.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_provider_registration.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_terminal_audit.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/tests/test_row_bindings_are_consumed.py`
- `S10` `M` `src/cadrumo/domain/modelos/row_models.py`
- `S10` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_source_boundary_and_enrollment.py`
- `S10` `M` `src/cadrumo/locales/ca/cli.yml`
- `S10` `M` `src/cadrumo/locales/ca/docs.yml`
- `S10` `M` `src/cadrumo/locales/ca/flows.yml`
- `S10` `M` `src/cadrumo/locales/en/cli.yml`
- `S10` `M` `src/cadrumo/locales/en/docs.yml`
- `S10` `M` `src/cadrumo/locales/en/flows.yml`
- `S10` `M` `src/cadrumo/locales/es/cli.yml`
- `S10` `M` `src/cadrumo/locales/es/docs.yml`
- `S10` `M` `src/cadrumo/locales/es/flows.yml`
- `S10` `M` `src/cadrumo/locales/hu/cli.yml`
- `S10` `M` `src/cadrumo/locales/hu/docs.yml`
- `S10` `M` `src/cadrumo/locales/hu/flows.yml`
- `S10` `verify:` `tree vs step text: 232 related_party_operation, 360 refund_operation, 182 donativo_donor row bindings and their provider kinds, registrations, observation models (donativo_bindings.py deleted) and row-set assemblers absent from src and dev; 360 declares family_dispositions.bindings` -> `pass`
- `S10` `verify:` `tree vs step text: 182 declares no family_dispositions.bindings in 2022-2023, 2024 or 2025 after its only bindings were removed (schema family coverage reports bindings blocked_pending_evidence)` -> `fail`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2022-2023/revision.toml`
- `S10` `verify:` `tree vs step text: 182 declares family_dispositions.bindings in 2022-2023, 2024 and 2025 (schema family coverage: bindings not_applicable in all three editions)` -> `pass`
- `S10` `verify:` `inspect_authoring_candidate (bundled source): publication_valid True, no findings` -> `pass`
- `S10` `verify:` `python -m dev.registry.edition_delta_migration --modelo 182 (non-applying): changed=False, equivalence and minimality passed` -> `pass`
- `S10` `verify:` `python -m dev.registry.form_layout generate --modelo 182 --check` -> `pass`
- `S11` `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py`
- `S11` `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/casillas/0001-declarations.toml`
- `S11` `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/bindings/0001-declarations.toml`
- `S11` `M` `src/cadrumo/adapters/persistence/profile/tests/test_source_resolver.py`
- `S11` `M` `src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py`
- `S11` `verify:` `ruff check + ruff format --check + ty check invoice_bindings.py` -> `pass`
- `S11` `verify:` `pytest test_modelo_347_contraparte_export_parity.py test_source_resolver.py -m 'unit or integration' (66)` -> `pass`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/constructs/0001-declarations.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/casillas/0001-declarations.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/form_layouts/0001-form-layout.toml`
- `S07` `M` `dev/registry/tests/test_ledger_renta_income_binding.py`
- `S07` `M` `src/cadrumo/application/aggregation/tests/test_ledger_income_chain_oracle_exempt.py`
- `S07` `M` `src/cadrumo/application/aggregation/tests/test_ledger_income_chain_oracle_rated.py`
- `S07` `M` `dev/registry/tests/test_ledger_income_chain_oracle_exempt.py`
- `S07` `M` `dev/registry/tests/test_ledger_income_chain_oracle_rated.py`
- `S07` `M` `src/cadrumo/application/modelo/tests/test_casilla_formula_values.py`
- `S07` `M` `src/cadrumo/domain/calculations/registry/tests/test_committed_registry.py`
- `S07` `M` `src/cadrumo/domain/calculations/registry/tests/test_formula_runtime.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_declarations_portfolio.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_declaration_summary.py`
- `S07` `M` `dev/registry/tests/test_formula_runtime.py`
- `S07` `verify:` `python -m dev.registry.edition_delta_migration --modelo 130 (non-applying): changed=False, equivalence and minimality passed` -> `pass`
- `S07` `verify:` `python -m dev.registry.form_layout generate --modelo 130 347 200 202 720 182 --check` -> `pass`
- `S07` `verify:` `ruff check + format --check on the 11 edited 130 test files` -> `pass`
- `S07` `verify:` `pytest 130 test set` -> `fail`
- `S06` `A` `.vault/research/2026-10-02-binding-consumer-closure-modelo-720-fx-research.md`
- `S06` `M` `.vault/adr/2026-07-05-modelo-720-row-carrier-adr.md`
- `S06` `M` `.vault/plan/2026-10-02-binding-consumer-closure-plan.md`
- `S06` `M` `.vault/index/binding-consumer-closure.index.md`
- `S06` `verify:` `vaultspec-core vault edit (dry-run, then expected-blob-hash guarded write)` -> `pass`
- `S06` `verify:` `vaultspec-core vault check all (no new errors on touched records)` -> `pass`
- `S07` `verify:` `pytest 130 S07 selection (166 passed)` -> `pass`
- `S06` `A` `src/cadrumo/core/isin.py`
- `S06` `A` `src/cadrumo/core/tests/test_isin.py`
- `S06` `A` `src/cadrumo/domain/foreign_assets/__init__.py`
- `S06` `A` `src/cadrumo/domain/foreign_assets/register.py`
- `S06` `A` `src/cadrumo/domain/foreign_assets/tests/__init__.py`
- `S06` `A` `src/cadrumo/domain/foreign_assets/tests/test_register.py`
- `S06` `A` `src/cadrumo/application/foreign_assets/__init__.py`
- `S06` `A` `src/cadrumo/application/foreign_assets/ports.py`
- `S06` `A` `src/cadrumo/adapters/persistence/profile/foreign_assets.py`
- `S06` `A` `src/cadrumo/adapters/persistence/profile/tests/test_foreign_asset_register_roundtrip.py`
- `S06` `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `S06` `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `S06` `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `S06` `M` `src/cadrumo/core/errors/registry/_domain_part3.py`
- `S06` `M` `src/cadrumo/locales/en/errors.yml`
- `S06` `M` `src/cadrumo/locales/es/errors.yml`
- `S06` `M` `src/cadrumo/locales/ca/errors.yml`
- `S06` `M` `src/cadrumo/locales/hu/errors.yml`
- `S06` `M` `src/cadrumo/locales/en/adapters.yml`
- `S06` `M` `src/cadrumo/locales/es/adapters.yml`
- `S06` `M` `src/cadrumo/locales/ca/adapters.yml`
- `S06` `M` `src/cadrumo/locales/hu/adapters.yml`
- `S06` `M` `dev/quality/metadata/import_load_targets.json`
- `S06` `verify:` `pytest W1 isin+register+roundtrip (47 passed)` -> `pass`
- `S06` `verify:` `pytest namespace registry gate (30 passed)` -> `pass`
- `S05` `M` `src/cadrumo/core/aggregation.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/_invoice_row_materialization.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/binding_provider.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/binding_terminal_audit.py`
- `S05` `M` `src/cadrumo/application/aggregation/source_mesh.py`
- `S05` `M` `src/cadrumo/application/aggregation/service.py`
- `S05` `M` `src/cadrumo/application/modelo/data_inventory.py`
- `S05` `M` `src/cadrumo/application/modelo/source_policy.py`
- `S05` `M` `src/cadrumo/application/state_projection.py`
- `S05` `M` `src/cadrumo/application/invoices/source_resolver.py`
- `S05` `M` `src/cadrumo/application/modelo/_m349_ledger_guard.py`
- `S05` `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `S05` `M` `src/cadrumo/_data/registry/aeat/facts/0084-iva-category-component-catalogue.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/bindings/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/constructs/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/form_layouts/0001-form-layout.toml`
- `S05` `M` `src/cadrumo/locales/en/cli.yml`
- `S05` `M` `src/cadrumo/locales/es/cli.yml`
- `S05` `M` `src/cadrumo/locales/ca/cli.yml`
- `S05` `M` `src/cadrumo/locales/hu/cli.yml`
- `S05` `M` `src/cadrumo/locales/en/docs.yml`
- `S05` `M` `src/cadrumo/locales/es/docs.yml`
- `S05` `M` `src/cadrumo/locales/ca/docs.yml`
- `S05` `M` `src/cadrumo/locales/hu/docs.yml`
- `S05` `M` `src/cadrumo/locales/en/flows.yml`
- `S05` `M` `src/cadrumo/locales/es/flows.yml`
- `S05` `M` `src/cadrumo/locales/ca/flows.yml`
- `S05` `M` `src/cadrumo/locales/hu/flows.yml`
- `S05` `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_349_registry_bindings.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/tests/_modelo_349_registry_support.py`
- `S05` `M` `dev/registry/tests/_modelo_349_registry_support.py`
- `S05` `M` `dev/registry/tests/test_creation.py`
- `S05` `M` `dev/registry/tests/test_iva_ledger_observation_role_cutover_static.py`
- `S05` `M` `src/cadrumo/application/aggregation/tests/test_precedence_ladder_conformance.py`
- `S05` `M` `src/cadrumo/adapters/persistence/profile/tests/test_source_resolver.py`
- `S05` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_dormant_m349_invoice_resolver_live.py`
- `S05` `M` `dev/registry/pipeline/candidate_compile_process.py`
- `S05` `M` `dev/registry/pipeline/tests/test_candidate_compile_process.py`
- `S05` `verify:` `inspect_authoring_candidate publication_valid` -> `pass`
- `S05` `verify:` `pytest S05 + 349 runtime set against generation 752c482a (all 349 tests passing)` -> `pass`
- `S05` `verify:` `pytest candidate compile process (4 passed)` -> `pass`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2023/bindings/0001-declarations.toml`
- `S07` `M` `src/cadrumo/application/aggregation/modelo_bindings.py`
- `S07` `verify:` `pytest 210 runtime + work form + IRNR binding set against generation ff975936 (58 passed)` -> `pass`
- `S07` `verify:` `check-bindings 210 findings` -> `pass`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/0001-declarations.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/revision.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/revision.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/form_layouts/0001-form-layout.toml`
- `S07` `M` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `S07` `M` `src/cadrumo/application/modelo/projection.py`
- `S07` `M` `src/cadrumo/application/modelo/profile_binding.py`
- `S07` `M` `src/cadrumo/application/modelo/calculation_diagnostics.py`
- `S07` `M` `src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`
- `S07` `M` `src/cadrumo/domain/contribuyente/family_profile.py`
- `S07` `M` `src/cadrumo/domain/contribuyente/descendant_facts.py`
- `S07` `D` `src/cadrumo/adapters/persistence/profile/tests/test_descendientes_count_desync_advisory.py`
- `S07` `M` `src/cadrumo/application/modelo/tests/test_guarderia_monthly_reaches_the_calculate_path.py`
- `S07` `M` `src/cadrumo/application/modelo/tests/test_derived_binding_advisory.py`
- `S07` `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_100_descendiente_entry_surface.py`
- `S07` `verify:` `pytest batch J non-CLI set against verification build 942fd998 (232 passed)` -> `pass`
- `S07` `verify:` `pytest domain contribuyente (495 passed)` -> `pass`
- `S07` `verify:` `inspect_authoring_candidate publication_valid` -> `pass`
- `S08` `M` `src/cadrumo/domain/calculations/registry/binding_targets.py`
- `S08` `A` `dev/registry/compiler/tests/test_relation_evidence_consumer.py`
- `S08` `verify:` `pytest relation evidence consumer + validate_bindings (15 passed)` -> `pass`
- `S08` `verify:` `check-bindings 193 findings cleared (10 left: 720 6, 347 4)` -> `pass`

## Notes

- `S02` Committed together with S03 and S04: the 390 2026 form-layout digest covers bindings S03 relocates, so S02 alone would not be a consistent tree.
- `S03` Grounding: 390 2022/2023 designs print no 2%, 7.5%, 0.26% or 1% boxes and 2022 no 0.62% box; 303 2022 design leaves every recargo row free (rate-specific rows are a 2023 novelty per the IVA 2022 manual).
- `S03` 184 member rows leave the applicability-grade 2022 floor, reversing that floor's earlier reduccion grounding, because nothing on the floor reads them.
- `S04` Re-scoped on evidence: the 45 vinculada casillas stay informational because Modelo232VinculadaRow detail rows fill them `(revision_replay_inputs);` their duplicate manual bindings are removed instead of bound, and informative modelos refuse bound casillas.
- `S07` S07 Partial: 200 SAL profile bindings retired (no reader; SAL dotacion computed from the `--sal-*` calculate options, Ley 44/2015 art. 14 unchanged); 202 INCN declared `non_calculation/profile_input` (LIS art. 40.3 modality, required-input gate); 130 retenciones-cumulative declared `non_calculation/application_calculation_handoff` under the accepted W01 routing-fact ruling. 100 guarderia, 130 duplicate/taxable-base, 193 2025 cross-check and 210 casilla `[5]` remain open pending src clearance and an owner decision on 210.
- `S07` S07 Scope addition authorized by the coordinator: consolidated the two 200 2025-y-siguientes `casilla_continuidad_evolutions` fragments into one (rows byte-identical, header quoting normalized).
- `S06` S06 Partial: prior-year valuation baselines declared `non_calculation/application_calculation_handoff,` read by the re-declaration advisory (RD 1065/2007 art. 42 bis: re-declaration only above a EUR 20.000 increase; `previous_filing` `filing_year_offset` resolution ignores applicability). The six `foreign_asset` row bindings remain open pending the owner decision on `type_2` export wiring.
- `S06` S06 Evidence caveat: the two 720 pytest modules recorded above read the published authority, so they prove the advisory path still works but not this source change; the change is proven only after republication (S09) and by the source-side gate (check-bindings 40 findings, no 720 baseline finding).
- `S10` S10 Rows recorded from the coordinator-supplied name-status of commit 80ef21d666 (no git run in this session). Step left open: modelo 182 lacks the binding family disposition the step text requires; Modelo232VinculadaRow remains by design (S04: detail rows fill the vinculada casillas).
- `S10` S10 Grounding for the 182 binding disposition: record designs aeat-dr-182-2021-2023, aeat-dr-182-2024 and aeat-dr-182-2025, tipo 2 registro de declarado positions 18-26, 36-75, 79-83, 84-96 and 132 (identical in all three); every hydrated casilla is informational or manual and no edition declares an export layout. Family dispositions are revision-local (2024 and 2025 did not inherit the 2022-2023 one), so each edition states its own and cites its own design.
- `S11` S11 Grounding: aeat-dr-347-2011 (Orden EHA/3378/2011) and aeat-dr-347-2025 (Orden HAC/1431/2025) type 1 pos. 136-144 count the type 2 declarado records ('se computará tantas veces como figure relacionado') and pos. 145-160 sum their pos. 83-98 amounts with sign. Intentional value change: the count is now records, not distinct parties (one counterparty under two claves counts 2), and both totals use the row family's own threshold (clave C floor included). Casillas decl.total-personas-entidades and decl.importe-total-anual are now bound (2025 inherits).
- `S11` S11 Open: 347 form-layout regeneration pending `(dev/registry/form_layout` is mid-split by another writer: NameError `node_slug);` `test_file_flow_verify.py` is dirty under another writer and was not edited.
- `S07` S07 130: retired modelo-130-actividad-economica-rendimiento-neto-cumulative (byte-identical duplicate of the taxable-base binding) and modelo-130-actividad-economica-ingresos-taxable-base-cumulative (no selection mechanism; casilla 01 is bound to the gross ingresos binding per AEAT 130 instructions casilla 01; casilla 03 is computed, RD 439/2007 art. 110.2). The `taxable_base_sum` fact keeps coverage through a synthetic sibling binding test.
- `S07` S07 Test run blocked by another writer: `dev/registry/compiler/loader_materialisation.py` raises NameError `LINEAGE_CLAIM_FIELDS` (mid-edit); an earlier run's 34 registry-validation errors came from this session's 347 casilla binding (reverted, see S11) and the stale 130 layout (regenerated).
- `S07` S07 Held until after the merge commit: modelo 100 guardería batch `(profile_binding.py,` projection.py and the entry-surface test are merge-owned; registry data restored to HEAD) and modelo 210 casilla `[5]` batch `(modelo_bindings.py).` Modelo 193: no data change needed; 2025 already overrides modelo-193-dep-123 to `factual_evidence.`
- `S11` S11 Correction: binding the two type 1 casillas was refused by `validate_informative_class_invariant` (informative modelos admit only informational and manual casillas); the casilla edit was reverted byte-exactly `(src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/casillas/0001-declarations.toml` back to HEAD; its ledger M row above is void). The totals' consumer must be the type 1 export fields (pos. 136-144, 145-160) reading the summary bindings, which is a generator mapping change in `dev/registry/mappings/modelo_347` applied with S12's target regeneration. Step stays open.
- `S06` S06 P1: row-carrier ADR amended (Route A) with the 2026-10-02 amendment; authorization basis 'Confirmed by the user on 2026-10-02 after review of the concrete rulings'. Currency section rewritten to the FX research: ECB reference rate (Ley 46/1998 art. 36), DGT-fixed rate dates per class and situation, real-estate euro freeze, last-declaration baselines, six advisory cases; grounding in research 2026-10-02-binding-consumer-closure-modelo-720-fx-research. Links added to binding-schema, source-casilla-integration, ledger-fx-conversion ADRs and the research; plan relates the ADR; S06 widened through step edit.
- `S06` S06 Held (merge-owned): `schema_exports.py,` export.py, `operation_definitions.py,` `operation_composition.py,` `binding_provider_registration.py` - W4 registration, W5 routes and W8 operation registration land after the merge commit.
- `S07` 130 E1/E2 closed: check-bindings 37 findings, none for 130; S07 stays open for 100 and 210 (held for the merge commit)
- `S06` W1 asset identity and register landed. Error-registry gate still red only on another writer's InvoiceAddValidationRefusedError (in-flight invoice refactor), not on the foreign-asset errors. W2-W8 remain.
- `S05` Intentional filing-value correction, not equivalence-preserving: casilla 04 iva-349-declarante-importe-rectificaciones now sums the rectified bases (fact `base_sum)` instead of rectification deltas, per aeat-dr-349-2020-current type 1 pos. 171-185 over type 2 pos. 153-165 and aeat-modelo-349-instructions casilla 04 ('base imponible rectificada').
- `S05` Blocker fix on the publication path: the candidate compiler's parent-lifetime watcher held a blocking stdin read that deadlocked numpy/OpenBLAS DLL init on Windows; it now polls the pipe with PeekNamedPipe. Authority republished as logical generation 752c482a91b9.
- `S07` 210 batch I implemented as an application handoff instead of the planned bound casilla: binding casilla `[5]` made the default manual mode stop prompting for it and dropped it from the filer-required set used by verification (silent under-declaration risk). `[5]` stays manual; m210-ledger-irnr-rendimientos-integros declares `non_calculation/application_calculation_handoff` (130 retenciones precedent) and the ledger IRNR resolver writes its ES-only value to `[5]` in ledger mode, replacing the all-jurisdiction fold redirect. TRLIRNR arts. 13.1 and 24; aeat-dr-210-2022 casilla `[5].`
- `S07` Batch J committed as 49feac35c0. CLI tests in the set fail with `REFUSED_LOCAL_RUNTIME` `runtime_unavailable,` including untouched modelo 130 cases, while the `local_runtime` lane is mid-edit: environmental, not J. `test_registry_contract` reads the published profile schema and passes only after the next publish (two publishes refused: Codex registry lane changed inputs mid-validation).
- `S07` Scope additions forced by the retirement: count-desync advisory retired (its premise, a binding reading the stored count, no longer exists); anualidades injector routed through `renta_family_profile_from_facts` to keep the by-index birth-date refusal; `descendientes_guarderia_count` and `gastos_guarderia_reales` removed as unused.
- `S11` Handed to the CADRUMO-ADMIN session on operator instruction (2026-10-03): modelo 347 is supported and binds to ledger invoice data. Resolver half already in HEAD `(invoice_bindings._resolve_m347_declarante_summary_values).` Binding the type 1 casillas is refused by `validate_informative_class_invariant` because 347 declares `calculation_class` = informative; resolution is that session's call. S12 signed-amount design offered with it.
- `S08` Section 0: `relation_evidence` consumer kind enrolled in the shared `binding_consumers` census (read by the gate, compiler and `registry_status),` selected through `relation_prefill_bindings_for_period` over declared periods so it counts exactly what calculation resolves. The 193 2025 dependency treatment override `(factual_evidence)` was already in the authored source. The S08 compiler refusal itself waits for zero residue (720 S06, 347 with CADRUMO-ADMIN).
