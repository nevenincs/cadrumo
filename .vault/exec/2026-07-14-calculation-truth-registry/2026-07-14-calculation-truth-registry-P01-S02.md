---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S02'
related:
  - "[[2026-07-14-calculation-truth-registry-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-truth-registry with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-07-14-calculation-truth-registry-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Land the Modelo 131 2024 export-roundtrip, historical date-axis, and live-filed-data-parser behaviour tests the legacy plan's own sub-bullets still list open and ## Scope

- `src/cadrumo/domain/calculations/registry/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Land the Modelo 131 2024 export-roundtrip, historical date-axis, and live-filed-data-parser behaviour tests the legacy plan's own sub-bullets still list open

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Confirm against the live test surface, per the legacy plan's `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md` sub-bullets, which of the three named test categories (export roundtrips, historical date-axis tests, live filed-data parser tests) were already covered for Modelo 131 2024 and which remained genuinely open now that the modulos-engine gap is closed.
- Confirm export roundtrips and live filed-data parser tests already parametrize the 2024 revision (`test_modelo_131_2024_dpa_territorial_reduction_fields_carry_specific_legal_basis`, `test_modelo_131_registry_bindings_cover_official_structured_records`, and `test_parser_extracts_modelo_131_current_year_profile_targets[2024]` / `test_parser_extracts_modelo_131_current_year_profile_targets_from_committed_synthetic_fixture[2024]`), so the genuinely open item is historical date-axis coverage for the newly-authored modulos-engine fragments.
- Author `test_modelo_131_modulos_engine_2024_backfill.py`, mirroring the sibling `test_modelo_131_modulos_engine_2026_rollforward.py` roll-forward pattern as a back-fill: independently-transcribed fase 1/2/3/4 parity proofs for two tabled activities (972.1 peluqueria, 721.2 autotaxis) against the bundled `orden-hfp-1359-2023.html` corpus text (not the registry formula under test), an untabled-epigrafe-resolves-to-zero proof, and a cross-revision parity proof (2024 and 2025 engines agree on the same tabled activity, since their coefficients are byte-identical).
- Author a dedicated `TestModulos2024DateAxisBoundaries` class proving the historical date-axis boundaries genuinely enforce temporal isolation: `select_revision` resolves 2023-12-31 to the flatter `2019-2023` revision (not 2024), 2025-01-01 to the `2025` revision (not 2024), and every `2024` calendar date to the `2024` revision; the `m131-modulos-coeficientes-2024` and `m131-modulos-reduccion-general-2024` parameters carry `valid_from`/`valid_to` scoped to 2024-01-01/2024-12-31; and the 2024 and 2025 snapshots each resolve only their own year-scoped coefficient-table parameter id, never the other year's.
- Run the new test file (9 tests, green) plus the full `src/cadrumo/domain/calculations/registry/tests/`, `src/cadrumo/adapters/inbound/declaracion/tests/`, `src/cadrumo/application/modelo/tests/`, and `src/cadrumo/application/calculations/tests/` directories (4795 of 4796 passed under `-n auto`; the single failure was a loader-cache race reproduced only under parallel xdist and confirmed green on sequential re-run, per `aeat-local-execution`).

## Outcome

Modelo 131 2024's historical date-axis coverage is now closed: the newly-authored modulos-engine fragments are proven grounded (independent fase 1-4 parity against the bundled 2024 Orden text), non-silently-partial (untabled epigrafes resolve to zero, never a fabricated figure), cross-revision-consistent (2024 and 2025 agree where the law agrees), and temporally isolated (the 2024 revision and its year-scoped coefficient parameter never leak across the 2023/2024 or 2024/2025 filing-year boundary). Export-roundtrip and live-filed-data-parser coverage for the 2024 revision was already landed by prior work and required no new tests. `uv run --no-sync pytest --collect-only -q` stays clean (12930 tests collected) and the full dependent test surface is green.

## Notes

The legacy plan's open bullet ("Export roundtrips, historical date-axis tests, and live filed-data parser tests remain open") predates the prior landing of the export-roundtrip and live-filed-data-parser coverage; only the date-axis category for the modulos engine specifically was genuinely open at this Step's start. No skips, xfails, or mocks were used; every parity figure is independently transcribed from the bundled AEAT corpus, not derived from the registry formula under test.
