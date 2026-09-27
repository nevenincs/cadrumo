---
tags:
  - '#exec'
  - '#registry-conformance-rectification'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:3fefe09b92a01e83a749cb87796313485962a4b42d206e2c2222371099a30728'
related:
  - "[[2026-09-27-registry-conformance-rectification-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `registry-conformance-rectification` ledger

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
- `S04` `M` `dev/registry/registry_collapse_verification.py`
- `S04` `M` `dev/registry/tests/test_registry_collapse_verification.py`
- `S04` `verify:` `pytest dev/registry/tests/test_registry_collapse_verification.py` -> `pass`
- `S01` `M` `dev/registry/registry_collapse_verification.py`
- `S01` `M` `dev/registry/tests/test_registry_collapse_verification.py`
- `S01` `verify:` `registry_collapse_verification --modelo 100 no_live_mutation` -> `pass`
- `S05` `M` `dev/registry/analysis/casilla_lineage_ledger.toml`
- `S05` `D` `dev/registry/tests/test_modelo_100_2024_profile_surface.py`
- `S05` `A` `dev/registry/tests/test_modelo_100_filing_surface_across_supported_years.py`
- `S05` `M` `dev/registry/tests/test_modelo_100_historical_pagos_fraccionados.py`
- `S05` `M` `dev/registry/tests/test_modelo_100_settlement_chain.py`
- `S05` `A` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/casillas/0001-declarations.toml`
- `S05` `R` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/constructs/0001-declarations.toml` -> `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/constructs/0001-declarations.toml`
- `S05` `A` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/dependency_classifications/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/formulas/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/parameters/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/revision.toml`
- `S05` `R` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/verification_predicates/0001-declarations.toml` -> `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/verification_predicates/0001-declarations.toml`
- `S05` `A` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/bindings/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/casillas/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/formulas/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/revision.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/dependency_classifications/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/parameters/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/revision.toml`
- `S05` `M` `src/cadrumo/adapters/inbound/borrador/tests/test_verification_chain_borrador.py`
- `S05` `M` `src/cadrumo/adapters/inbound/declaracion/tests/_verification_chain_m100_support.py`
- `S05` `M` `src/cadrumo/adapters/inbound/declaracion/tests/_verification_chain_support.py`
- `S05` `M` `src/cadrumo/adapters/inbound/declaracion/tests/test_verification_chain_m100_corpus_limited.py`
- `S05` `M` `src/cadrumo/application/modelo/tests/test_settlement_grade_advisory.py`
- `S05` `R` `src/cadrumo/domain/calculations/registry/tests/test_m100_2024_final_settlement_chain_wiring.py` -> `src/cadrumo/domain/calculations/registry/tests/test_m100_final_settlement_chain_manual_anchor.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_anualidades_separate_escala_multiyear.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_historical_pagos_fraccionados.py`
- `S05` `M` `src/cadrumo/domain/calculations/registry/tests/test_registry_scenarios.py`
- `S05` `M` `src/cadrumo/domain/renta/tests/test_first_slice_routing.py`
- `S05` `A` `src/cadrumo/entrypoints/cli/tests/test_modelo_100_bindings_list_across_supported_years.py`
- `S05` `M` `src/cadrumo/locales/ca/modelo/schema/100.yml`
- `S05` `M` `src/cadrumo/locales/en/modelo/schema/100.yml`
- `S05` `M` `src/cadrumo/locales/es/modelo/schema/100.yml`
- `S05` `M` `src/cadrumo/locales/hu/modelo/schema/100.yml`
- `S05` `M` `src/cadrumo/tests/fixtures/borrador/generate.py`
- `S05` `M` `src/cadrumo/tests/fixtures/borrador/modelo_100_2022.json`
- `S05` `M` `src/cadrumo/tests/fixtures/borrador/modelo_100_2022.pdf`
- `S05` `M` `src/cadrumo/tests/fixtures/borrador/modelo_100_2023.json`
- `S05` `M` `src/cadrumo/tests/fixtures/borrador/modelo_100_2023.pdf`
- `S05` `verify:` `just check-registry-gate` -> `pass`
- `S13` `M` `dev/registry/registry_collapse_verification.py`
- `S13` `M` `dev/registry/tests/test_registry_collapse_verification.py`
- `S13` `verify:` `python -m dev.registry.registry_collapse_verification --modelo 100 (complete, indexed 3307 coordinates)` -> `pass`
- `S07` `M` `dev/registry/compiler/modelo_projections.py`
- `S07` `M` `dev/registry/tests/test_modelo_100_filing_surface_across_supported_years.py`
- `S07` `A` `dev/registry/tests/test_modelo_100_parameter_projection_across_horizon.py`
- `S07` `M` `dev/registry/tests/test_modelo_projections.py`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/parameters/0001-declarations.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2021/revision.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/parameters/0001-declarations.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/revision.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/parameters/0001-declarations.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/revision.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/revision.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0001-declarations.toml`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/revision.toml`
- `S07` `verify:` `just check-registry-gate` -> `pass`
- `S07` `M` `dev/registry/tests/test_modelo_100_parameter_projection_across_horizon.py`
- `S07` `verify:` `pytest dev (no failure beyond main; lane gate green after removing the merged worktree)` -> `pass`
- `S06` `A` `dev/registry/tests/test_activity_asset_authority_across_supported_years.py`
- `S06` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/parameters/0001-declarations.toml`
- `S06` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/parameters/0001-declarations.toml`
- `S06` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2023/revision.toml`
- `S06` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/parameters/0001-declarations.toml`
- `S06` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/revision.toml`
- `S06` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0001-declarations.toml`
- `S06` `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/revision.toml`
- `S06` `verify:` `just check-registry, check-bindings, check-registry-gate` -> `pass`
- `S08` `M` `dev/registry/tests/test_activity_asset_authority_across_supported_years.py`
- `S08` `M` `src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py`
- `S08` `M` `src/cadrumo/entrypoints/cli/_actividad_asset_cli.py`
- `S08` `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `S08` `verify:` `ruff check, ruff format, ty on touched files` -> `pass`
- `S09` `M` `src/cadrumo/domain/renta/actividad_asset/claims.py`
- `S09` `M` `src/cadrumo/domain/renta/actividad_asset/tests/test_claims.py`
- `S09` `verify:` `pytest src/cadrumo/domain/renta/actividad_asset/tests/test_claims.py (7 passed)` -> `pass`
- `S09` `M` `src/cadrumo/_data/registry/aeat/legal/irpf.toml`
- `S09` `M` `src/cadrumo/application/aggregation/withholding_recognition.py`
- `S09` `M` `src/cadrumo/application/aggregation/tests/test_withholding_recognition.py`
- `S09` `M` `src/cadrumo/adapters/persistence/profile/tests/test_ledger_payment_withholding.py`
- `S09` `M` `src/cadrumo/adapters/persistence/profile/tests/test_withholding_monthly_filer_capture.py`
- `S09` `verify:` `just check-registry, check-bindings, check-registry-gate` -> `pass`
- `S10` `M` `src/cadrumo/application/aggregation/m193_phase_materialization.py`
- `S10` `M` `src/cadrumo/application/aggregation/withholding_source.py`
- `S10` `M` `src/cadrumo/application/modelo/m193_settled_row_gate.py`
- `S10` `M` `src/cadrumo/application/aggregation/tests/withholding_filer_profile_support.py`
- `S10` `M` `src/cadrumo/adapters/persistence/profile/tests/ledger_capital_support.py`
- `S10` `M` `src/cadrumo/adapters/persistence/profile/tests/test_ledger_payment_capital_withholding.py`
- `S10` `M` `src/cadrumo/adapters/persistence/profile/tests/test_withholding_producer.py`
- `S10` `M` `src/cadrumo/adapters/persistence/profile/tests/test_withholding_source_m193_phases.py`
- `S10` `M` `src/cadrumo/entrypoints/cli/tests/test_ledger_payment_capital_withholding_aggregate_cli.py`
- `S10` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_m193_disclosure_phase_calculation.py`
- `S10` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_m193_settled_amount_advisory_calculate.py`
- `S10` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_m193_settled_row_export_gate.py`
- `S10` `M` `src/cadrumo/entrypoints/tests/test_m123_count_authority_gate.py`
- `S10` `M` `src/cadrumo/entrypoints/tests/test_m193_settled_row_file_verify_gate.py`
- `S10` `verify:` `pytest withholding and 193 test set (3653 passed; 9 failures identical on main)` -> `pass`
- `S02` `M` `dev/registry/edition_delta_migration.py`
- `S02` `A` `dev/registry/tests/test_edition_delta_drop_restatement.py`
- `S02` `verify:` `pytest dev/registry (2965 passed; the one failure passes alone)` -> `pass`
- `S03` `M` `dev/registry/registry_collapse_verification.py`
- `S03` `M` `dev/registry/tests/test_registry_collapse_verification.py`
- `S03` `verify:` `pytest dev/registry/tests/test_registry_collapse_verification.py` -> `pass`

## Notes

- `S04` Classified as a comparison artefact: family_dispositions is a typed Mapping; shares the S01 commit because both change the same comparator module
- `S05` Modelo 100 2022 casilla 0670 stays manual: the official dictionary label signs of 1913 and 1916 contradict the manual; returned to the operator for ruling.
- `S05` The final-settlement manual-anchor test still names its manual ejercicio as a literal until the evidence-derived manual-edition selector from the test-year scrub is merged.
- `S07` Two parameters keep their stated windows: the renewables availability flag is keyed on transaction_date, and renta-guarderia-incremento-cap-anual exists only in the 2024 edition.
- `S07` Correction: editions carried the closed rows of earlier editions, which table readers such as the accumulated-cuota gate read as current law; each edition now states only its in-force rows, with a progressive bracket table kept whole.
- `S10` A settled-row contributor persisted without its accrual year is now counted as settled in every supported year after the floor, where it was only counted after 2025: the gate over-refuses rather than lets a settled row through.
- `S02` Registry-wide the fix brings 22 storage-rooted editions across 11 modelos into assessment; none currently states a droppable restatement, so no registry source changes.

