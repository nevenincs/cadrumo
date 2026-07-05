---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S10'
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
     The S10 and 2026-07-05-modelo-720-prior-year-baseline-plan placeholders are machine-filled by
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
     The Update the central foreign-asset class taxonomy tests to pin the official M720 clave set and any Modelo 721 split and ## Scope

- `src/aeat/core/tests/test_foreign_asset_obligation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update the central foreign-asset class taxonomy tests to pin the official M720 clave set and any Modelo 721 split

## Scope

- `src/aeat/core/tests/test_foreign_asset_obligation.py`

## Description

- Updated the core obligation tests so every `ForeignAssetClass` remains mapped to a regulatory obligation group.
- Added coverage proving the new IIC class maps to the RD 1065/2007 art. 42 ter valores/derechos/seguros block.
- Added a central official-code test pinning the Modelo 720 position-102 code map to `C`, `V`, `I`, `S`, and `B`.
- Added coverage proving `VIRTUAL_CURRENCY` is excluded from the Modelo 720 code map and remains a Modelo 721 split.

## Outcome

- The core taxonomy test now fails if a future worker removes IIC, maps real estate back to `I`, or leaks virtual currency into Modelo 720.
- The existing totality test continues to guard that every enum member has an obligation group.

## Notes

- Focused verification passed: `uv run --no-sync pytest -q -n 0 src/aeat/core/tests/test_foreign_asset_obligation.py src/aeat/application/aggregation/tests/test_foreign_assets.py --tb=short` reported 42 passed.
- Broader phase verification passed with `src/aeat/application/aggregation/tests/test_per_modelo_service.py` included and reported 67 passed.
- Focused ruff verification passed on the touched source and test files.
