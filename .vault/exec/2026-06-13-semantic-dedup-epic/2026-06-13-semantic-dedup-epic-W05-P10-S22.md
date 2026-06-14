---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S22'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S22 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C1-3 Replace the inline euro-cent quantize outlier with round_to_cents and ## Scope

- `src/aeat/application/filing/_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C1-3 Replace the inline euro-cent quantize outlier with round_to_cents

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Re-verified at HEAD: the money-export encoder re-derived euro-cent rounding
  inline (`abs(amount).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)`) while the
  sibling fichero encoder `_record_spec` already used canonical `round_to_cents`.
- Imported `round_to_cents` from `core.money` and replaced the inline quantize.
- Dropped the now-unused `ROUND_HALF_UP` import; retained `_MONEY_QUANT` for the
  constraint-divergent comparison quantize at the verify site (no rounding mode).

## Outcome

Committed as `ae94c2ffe`, tagged `relocation:round_to_cents`. Ruff clean; 41
filing export tests green. Behaviour-identical (CENT=0.01, ROUND_HALF_UP).

## Notes

The comparison-equality quantize at the verify site was intentionally left
untouched (Pass-2 audit constraint-divergent: context-default rounding).
