---
tags:
  - '#exec'
  - '#registry-conformance-rectification'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:a7553b4f378d95140fc29d8ecf5f145d7f338c2d23abc9a095f2e007494870da'
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

## Notes

- `S04` Classified as a comparison artefact: family_dispositions is a typed Mapping; shares the S01 commit because both change the same comparator module
- `S05` Modelo 100 2022 casilla 0670 stays manual: the official dictionary label signs of 1913 and 1916 contradict the manual; returned to the operator for ruling.
- `S05` The final-settlement manual-anchor test still names its manual ejercicio as a literal until the evidence-derived manual-edition selector from the test-year scrub is merged.
- `S07` Two parameters keep their stated windows: the renewables availability flag is keyed on transaction_date, and renta-guarderia-incremento-cap-anual exists only in the 2024 edition.

