---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S09'
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
     The S09 and 2026-07-05-modelo-720-prior-year-baseline-plan placeholders are machine-filled by
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
     The Migrate the typed M720 asset-code map so real estate emits B and unsupported or split-out classes cannot emit the wrong record-design clave and ## Scope

- `src/aeat/application/aggregation/_foreign_assets.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate the typed M720 asset-code map so real estate emits B and unsupported or split-out classes cannot emit the wrong record-design clave

## Scope

- `src/aeat/application/aggregation/_foreign_assets.py`

## Description

- Added a distinct `ForeignAssetClass.COLLECTIVE_INVESTMENT` member for the official Modelo 720 IIC class.
- Corrected the typed enum comments and values so real estate is the official Modelo 720 `B` class and virtual currency is labelled as the Modelo 721 sibling.
- Centralized the official Modelo 720 position-102 code map as `MODELO_720_FOREIGN_ASSET_CLASS_CODES`.
- Updated the application projection helper to consume the central map instead of its previous local `MappingProxyType`.
- Removed virtual currency from the Modelo 720 projection map so unsupported sibling classes raise instead of emitting a wrong record-design clave.

## Outcome

- Modelo 720 row projection now maps account/security/IIC/insurance/real-estate to `C`/`V`/`I`/`S`/`B`.
- `REAL_ESTATE` no longer emits `I`.
- `VIRTUAL_CURRENCY` has no Modelo 720 class-code output and fails closed when selected for Modelo 720 row projection.
- No binding source kind, resolver convention, or validator convention was added.

## Notes

- Verification was run with S10/S11 because the source migration, central taxonomy tests, and row-projection tests are coupled.
- Broader phase verification passed: `uv run --no-sync pytest -q -n 0 src/aeat/core/tests/test_foreign_asset_obligation.py src/aeat/application/aggregation/tests/test_foreign_assets.py src/aeat/application/aggregation/tests/test_per_modelo_service.py --tb=short` reported 67 passed.
