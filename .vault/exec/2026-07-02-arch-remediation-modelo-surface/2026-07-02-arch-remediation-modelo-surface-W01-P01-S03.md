---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S03'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-modelo-surface with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
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
     The Delete the M210 sentinel rate constants from the domain formula runtime in the same atomic change that lands the typed outcome, leaving no tolerance window in which both channels exist and ## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete the M210 sentinel rate constants from the domain formula runtime in the same atomic change that lands the typed outcome, leaving no tolerance window in which both channels exist

## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py`

## Description

- Delete the M210 negative Decimal sentinel constants and public aliases from the formula runtime.
- Remove sentinel exports from the registry package surface.
- Sweep M210 sentinel wording from the touched runtime and M210 helper/test comments.

## Outcome

No `M210_*_SENTINEL`, `M210_RATE_SENTINELS`, or `_rewrite_m210_sentinels` symbols remain under `src`.

## Notes

The sentinel deletion landed in the same patch set as the typed outcome channel.
