---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S35'
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
     The S35 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C2 Replace module-local _STRICT_FROZEN re-declarations with the aliased canonical import and ## Scope

- `src/aeat/core/_models.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C2 Replace module-local _STRICT_FROZEN re-declarations with the aliased canonical import

## Scope

- `src/aeat/core/_models.py`

## Description

- Found ten module-local `_STRICT_FROZEN = ConfigDict(strict=True, frozen=True,
  extra="forbid")` re-declarations (single- and multi-line, with/without
  `: Final`), all peer-clean and exactly canonical-shape.
- Scripted (dry-run-reviewed) the removal of each declaration + insertion of
  `from <depth>core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN`; `ruff --fix`
  dropped the now-unused `ConfigDict`/`Final` imports and sorted.

## Outcome

Committed as `b84d73f8b`, tagged `relocation:STRICT_FROZEN_CONFIG` (10 files,
+23/-45). Ruff clean; collect-only clean (897 collected); 459
auth/iva_compensation/calculations/reconciliation tests green.

## Notes

Excluded `_cross_period_clean_state` (peer-WIP at edit time) and
`core/json_contract._STRICT_FROZEN_CONFIG` (carries `validate_assignment=True`
— constraint-divergent, keeps its own config per the core/_models carve-out).
