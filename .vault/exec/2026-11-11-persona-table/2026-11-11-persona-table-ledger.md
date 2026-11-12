---
tags:
  - '#exec'
  - '#persona-table'
date: '2026-11-11'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:5c3e0eac67ed273a27d6a910e07c891e6bb296413c30a3389a1f152aecc795ab'
related:
  - "[[2026-11-11-persona-table-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `persona-table` ledger

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

- `S01` `M` `dev/acceptance/persona_table/rows.py`
- `S01` `M` `dev/acceptance/persona_table/baseline`
- `S01` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S01` `by:` `ACCEPTANCE`
- `S02` `M` `dev/acceptance/persona_table/rows.py`
- `S02` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S02` `by:` `ACCEPTANCE`
- `S03` `M` `dev/acceptance/persona_table/sweep.py`
- `S03` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S03` `by:` `ACCEPTANCE`
- `S04` `M` `dev/fixtures/personas`
- `S04` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S04` `by:` `ACCEPTANCE`
- `S05` `M` `dev/fixtures/personas`
- `S05` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S05` `by:` `ACCEPTANCE`
- `S06` `M` `dev/fixtures/personas`
- `S06` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S06` `by:` `ACCEPTANCE`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/100`
- `S07` `verify:` `persona table at feature/tui 83cea4b998 (train t6)` -> `pass`
- `S07` `by:` `ACCEPTANCE`
- `S08` `M` `src/cadrumo/application/aggregation`
- `S08` `verify:` `persona table at feature/tui 83cea4b998 (train t6)` -> `pass`
- `S08` `by:` `ACCEPTANCE`
- `S10` `M` `src/cadrumo/application/filing`
- `S10` `verify:` `persona table at feature/tui 83cea4b998 (train t6)` -> `pass`
- `S10` `by:` `ACCEPTANCE`
- `S13` `M` `src/cadrumo/_data/registry/aeat/modelos/347`
- `S13` `verify:` `persona table at feature/tui 83cea4b998 (train t6)` -> `pass`
- `S13` `by:` `ACCEPTANCE`
- `S09` `M` `src/cadrumo/_data/registry/aeat/modelos/100`
- `S09` `verify:` `persona table at feature/tui 90910e5cc5 (train t14), minorista 100 2023-2025` -> `pass`
- `S09` `by:` `ACCEPTANCE`
- `S11` `M` `dev/fixtures/personas`
- `S11` `verify:` `persona table at feature/tui 90910e5cc5 (train t14), minorista 100 2023-2025 export` -> `pass`
- `S11` `by:` `ACCEPTANCE`
- `S04` `verify:` `persona table at feature/tui 674c6ff701 (train t23), Modelo 130 69/69 compared and green, floor year 2022 by the S31 attestation` -> `pass`
- `S05` `verify:` `persona table at feature/tui 674c6ff701 (train t23), every Modelo 130 row compared and green 69/69` -> `pass`
- `S06` `M` `dev/acceptance/persona_table/counterparties.py`
- `S06` `verify:` `persona table at feature/tui 674c6ff701 (train t23), 111 16/16 115 16/16 180 4/4 190 4/4 compared and green` -> `pass`
- `S13` `verify:` `persona table at feature/tui 674c6ff701 (train t23), 390 20/20 349 16/16 347 16/16 compared and green` -> `pass`
- `S12` `verify:` `persona_table run --tree ed243d5bd7 (t32b, 266/278): 303 x every persona/year/quarter compared on role iva-resultado-regimen-general and exported` -> `pass`
- `S12` `by:` `ACCEPTANCE`
- `S14` `verify:` `persona_table run --tree ed243d5bd7 (t32b, 266/278): minorista-recargo 303 rows (recargo) green` -> `pass`
- `S14` `by:` `ACCEPTANCE`
- `S30` `verify:` `persona_table run --tree ed243d5bd7 (t32b, 266/278): 180/190 perceptor names compared upper-unaccented in the exported file, PAGOS 109/109` -> `pass`
- `S30` `by:` `ACCEPTANCE`
- `S31` `verify:` `persona_table run --tree ed243d5bd7 (t32b, 266/278): floor-source 0 and the floor-year 130/100 rows green since t23 on the S31 attestation` -> `pass`
- `S31` `by:` `ACCEPTANCE`
- `S51` `verify:` `persona_table run --tree ed243d5bd7 (t32b, 266/278): intracomunitario-desarrollador 100 2022-2025 green on 0218/0222 since t30b` -> `pass`
- `S51` `by:` `ACCEPTANCE`
- `S43` `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2019-2022/bindings/0001-declarations.toml`
- `S43` `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2019-2022/casillas/0001-declarations.toml`
- `S43` `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2019-2022/constructs/0001-declarations.toml`
- `S43` `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2019-2022/dependency_classifications/0001-declarations.toml`
- `S43` `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2019-2022/form_layouts/0001-form-layout.toml`
- `S43` `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2023-2024/form_layouts/0001-form-layout.toml`
- `S43` `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2023-2024/revision.toml`
- `S43` `D` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/bindings/0001-declarations.toml`
- `S43` `D` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/dependency_classifications/0001-declarations.toml`
- `S43` `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/revision.toml`
- `S43` `M` `.vault/adr/2026-06-19-m202-first-period-attestation-adr.md`
- `S43` `M` `src/cadrumo/adapters/persistence/profile/tests/test_cross_period_clean_state.py`
- `S43` `M` `src/cadrumo/adapters/persistence/profile/tests/test_modelo_200_202_pagos_fraccionados_fold.py`
- `S43` `M` `src/cadrumo/application/calculations/cross_period_clean_state.py`
- `S43` `A` `src/cadrumo/application/calculations/modelo_202_base_source.py`
- `S43` `M` `src/cadrumo/application/calculations/relation_prefill.py`
- `S43` `M` `src/cadrumo/application/calculations/tests/test_cross_period_first_year_fractional.py`
- `S43` `M` `src/cadrumo/application/calculations/tests/test_first_year_modalidad_cuota_no_wizard_catalogue.py`
- `S43` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_200_first_year_cuota_e2e.py`
- `S43` `M` `src/cadrumo/_data/registry/aeat/facts/0101-modelo-202-applicability-catalogue.toml`
- `S43` `A` `src/cadrumo/adapters/persistence/profile/tests/test_modelo_202_instalment_facts.py`
- `S43` `M` `src/cadrumo/application/overview/applicability_evidence.py`
- `S43` `M` `src/cadrumo/application/overview/calendar.py`
- `S43` `M` `src/cadrumo/application/overview/calendar_models.py`
- `S43` `A` `src/cadrumo/application/overview/modelo202_instalment.py`
- `S43` `A` `src/cadrumo/application/overview/modelo202_instalment_evidence.py`
- `S43` `M` `src/cadrumo/application/overview/read_calendar_item_projection.py`
- `S43` `A` `src/cadrumo/application/overview/tests/test_calendar_modelo_202_instalment.py`
- `S43` `M` `src/cadrumo/domain/calculations/registry/applicability_modelo202.py`
- `S43` `M` `src/cadrumo/entrypoints/cli/overview_rendering.py`
- `S43` `M` `src/cadrumo/entrypoints/cli/overview_results.py`
- `S43` `A` `src/cadrumo/entrypoints/cli/tests/test_overview_modelo_202_instalment_doors.py`
- `S43` `M` `src/cadrumo/entrypoints/overview_read_composition.py`
- `S43` `verify:` `pytest test_calendar_modelo_202_instalment test_modelo_202_instalment_facts test_overview_modelo_202_instalment_doors test_calendar_legal_entity test_cross_period_clean_state test_cross_period_first_year_fractional` -> `pass`
- `S43` `verify:` `lint-imports --config .importlinter` -> `pass`
- `S43` `by:` `implementation-engineer`
- `S43` `M` `dev/quality/metadata/import_load_targets.cadrumo.json`
- `S43` `M` `dev/quality/metadata/import_load_targets.json`
- `S43` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S43` `verify:` `operation_contract_manifest.generate --check=pass; import_load_probe --compile-targets` -> `pass`
- `S43` `M` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `S43` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_profile_schema_migration.py`
- `S43` `A` `src/cadrumo/adapters/persistence/storage/custody/tests/test_profile_schema_migration_art_40_3_election.py`
- `S43` `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_profile_schema_migration_rental_tier.py`
- `S43` `M` `src/cadrumo/domain/user_profile/schema_migration.py`
- `S43` `M` `src/cadrumo/domain/user_profile/tests/test_schema.py`
- `S43` `verify:` `pytest custody schema-migration tests and domain/user_profile/tests=pass; registry conformance valid, runtime-load, integrity` -> `pass`
- `S43` `M` `src/cadrumo/application/overview/calendar_warnings.py`
- `S43` `M` `src/cadrumo/application/overview/modelo202_instalment_evidence.py`
- `S43` `A` `src/cadrumo/application/overview/tests/test_modelo_202_art_40_3_election_reader.py`
- `S43` `verify:` `pytest application/overview/tests=pass; ty and lint-imports` -> `pass`
- `S43` `M` `.vault/adr/2026-11-11-modelo-202-obligation-adr.md`
- `S43` `M` `src/cadrumo/adapters/persistence/profile/tests/test_modelo_202_instalment_facts.py`
- `S43` `M` `src/cadrumo/application/overview/modelo202_instalment.py`
- `S43` `M` `src/cadrumo/application/overview/tests/test_calendar_modelo_202_instalment.py`
- `S43` `M` `src/cadrumo/entrypoints/cli/tests/test_overview_modelo_202_instalment_doors.py`
- `S43` `M` `src/cadrumo/locales/ca/cli.yml`
- `S43` `M` `src/cadrumo/locales/en/cli.yml`
- `S43` `M` `src/cadrumo/locales/es/cli.yml`
- `S43` `M` `src/cadrumo/locales/hu/cli.yml`
- `S43` `verify:` `pytest Modelo 202 instalment overview, persistence and cli tests (148 passed)` -> `pass`
- `S43` `M` `docs/_sequences/how-to/profile-setup/profile-setup-flag-help.json`
- `S43` `M` `docs/_sequences/how-to/protect-data-access/protect-data-access-machine-secret-help.json`
- `S43` `M` `src/cadrumo/_data/registry/aeat/facts/0096-ley-49-2002-profile-binding-catalogue.toml`
- `S43` `M` `src/cadrumo/application/wizard/command_parameters.py`
- `S43` `M` `src/cadrumo/application/wizard/setup_identity_sections.py`
- `S43` `M` `src/cadrumo/domain/user_profile/setup_answers.py`
- `S43` `M` `src/cadrumo/entrypoints/cli/config/profile_command_specs.py`
- `S43` `M` `src/cadrumo/locales/ca/profile.yml`
- `S43` `M` `src/cadrumo/locales/ca/wizard.yml`
- `S43` `M` `src/cadrumo/locales/en/profile.yml`
- `S43` `M` `src/cadrumo/locales/en/wizard.yml`
- `S43` `M` `src/cadrumo/locales/es/profile.yml`
- `S43` `M` `src/cadrumo/locales/es/wizard.yml`
- `S43` `M` `src/cadrumo/locales/hu/profile.yml`
- `S43` `M` `src/cadrumo/locales/hu/wizard.yml`
- `S43` `verify:` `pytest application/wizard/tests domain/deadlines/tests and dev/locales/tests (2896 passed)` -> `pass`

## Notes

- `S01` runner, committed per-row baseline (6f7b81b8e8) and summary separating pass from history-filed, unverified, unsupported, floor-source; t3 195/278
- `S02` 278 rows: every applicable obligation and every history return per persona and supported year from the registry envelope; only sociedad 200 (P02) has no stated values
- `S03` quarters filed locally in chain order before the annual return; Modelo 130 2T-4T 2023-2025 green for all four 130 personas
- `S04` Modelo 130 1T green 2023-2025 for every persona and alta-reciente 2022-2026; the floor year 2022 is floor-source (prior-year Renta below the envelope), carried by S31
- `S05` every Modelo 130 row above the floor year passes with stated, sourced casillas (53 pass)
- `S06` Modelo 111 16/16, 115 16/16, 180 4/4, 190 4/4 green
- `S07` Modelo 100 2024 calculates for all seven M100 personas (six green; minorista red only at export, refund account, S11)
- `S08` Modelo 100 2023-2025 calculate and verify pass for every 130 persona after its quarters are filed
- `S10` Modelo 100 2023-2025 verify passes for every persona, asalariada-familia's descendants included (0166 and names served)
- `S13` 390 20/20, 349 16/16, 347 12/12 green; fontanero 347 4/4 expected-refusal `REFUSED_MODELO_EXPORT_VALUE_OVERFLOW` at export
- `S14` No persona owes a prorrata 303; the prorrata part has no table row to assert.
- `S14` PRIME order 04:2x: S14 closes for the recargo rows only; the prorrata part moved to its own open Step S54 (no persona owes a prorrata 303).
