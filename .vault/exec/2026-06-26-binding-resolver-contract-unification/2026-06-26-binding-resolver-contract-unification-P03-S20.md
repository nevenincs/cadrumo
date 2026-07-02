---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S20'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-resolver-contract-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S20 and 2026-06-26-binding-resolver-contract-unification-plan placeholders are machine-filled by
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
     The Foreign-assets 720 correctness gate follow-up and ## Scope

- `src/aeat/application/aggregation/tests/test_per_modelo_service.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Foreign-assets 720 correctness gate follow-up

## Scope

- `src/aeat/application/aggregation/tests/test_per_modelo_service.py`

## Description

- Add a Modelo 720 per-modelo correctness gate in `src/aeat/application/aggregation/tests/test_per_modelo_service.py`.
- Build a real mixed foreign-asset fixture with two account assets whose class total crosses the 50,000 EUR reporting floor and one sub-floor security control that must be excluded from declarable rows.
- Assert the per-modelo service output equals the prior `aggregate_foreign_assets_720` result.
- Project that prior aggregate through `_registry_observations_from_foreign_assets_aggregation` and the live M720 registry `resolve_foreign_asset_binding_row_values`, asserting the exact row-indexed binding map for the two declarable account rows.
- Call `ForeignAssetsAggregationSourceResolver.resolve(...)` against the live M720 snapshot and assert the resolver selects the same declarable provenance and ledger transaction id while leaving scalar `binding_values` empty.

## Outcome

- The aggregate-to-live-registry row projection is proven exact for the M720 fixture.
- P03.S20 remains unchecked. The current `CalculationSourceResolution` envelope has scalar `binding_values` and typed `detail_rows`, but no row-indexed binding-value channel for `dict[(binding_id, row_index), Decimal | str]`; `ForeignAssetsAggregationSourceResolver` validates the row values and discards them instead of returning them.
- Formal blocker: `DFR-D9-P03-S20-M720-ROW-INDEXED-ENVELOPE`. Completing S20 exactly as written requires a coordinator-approved M720 row carrier strategy before the resolver can expose the prior aggregate output through the live mesh.
- Verification passed:
  - `uv run --no-sync ruff check src/aeat/application/aggregation/tests/test_per_modelo_service.py`
  - `uv run --no-sync python -m py_compile src/aeat/application/aggregation/tests/test_per_modelo_service.py`
  - `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_per_modelo_service.py::test_foreign_assets_m720_registry_rows_match_prior_aggregate_exactly src/aeat/application/aggregation/tests/test_foreign_assets.py::TestForeignAssetSourceResolver::test_resolver_validates_declarable_m720_rows_against_live_registry`
  - `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_per_modelo_service.py src/aeat/application/aggregation/tests/test_foreign_assets.py`

## Notes

- No P03.S20 plan check was run. This record is evidence plus formal deferral inventory, not closure.
- No resolver-envelope, registry, resolver-enrollment, or `_calculation_actions.py` edit was made.
