---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S11'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-720-prior-year-baseline with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-07-05-modelo-720-prior-year-baseline-plan placeholders are machine-filled by
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
     The Add M720 row-projection tests proving real estate emits B and virtual currency cannot be emitted through Modelo 720 and ## Scope

- `src/aeat/application/aggregation/tests/test_foreign_assets.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add M720 row-projection tests proving real estate emits B and virtual currency cannot be emitted through Modelo 720

## Scope

- `src/aeat/application/aggregation/tests/test_foreign_assets.py`

## Description

- Added a live Modelo 720 row-projection test that aggregates declarable IIC and real-estate observations, resolves them through the registry row bindings, and proves the emitted row class codes are `I` and `B`.
- Added a fail-closed projection test where a declarable virtual-currency observation reaches row projection and raises instead of producing a Modelo 720 row.

## Outcome

- The row-binding path now proves real estate emits `B` and IIC emits `I` through the same registry resolver used by the production aggregation path.
- Virtual currency cannot be silently emitted through Modelo 720.

## Notes

- Focused verification passed: `uv run --no-sync pytest -q -n 0 src/aeat/core/tests/test_foreign_asset_obligation.py src/aeat/application/aggregation/tests/test_foreign_assets.py --tb=short` reported 42 passed.
- Broader phase verification passed with `src/aeat/application/aggregation/tests/test_per_modelo_service.py` included and reported 67 passed.
