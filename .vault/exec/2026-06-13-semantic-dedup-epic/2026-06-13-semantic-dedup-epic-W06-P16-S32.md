---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S32'
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
     The S32 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The A3 Delegate _display_decimal and _decimal_to_string to core.decimal.format_decimal and ## Scope

- `src/aeat/application/ledger/_actions_common.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# A3 Delegate _display_decimal and _decimal_to_string to core.decimal.format_decimal

## Scope

- `src/aeat/application/ledger/_actions_common.py`

## Description

- Proved `format_decimal(v, normalize=True)` == `format(v.normalize(), "f")` and
  `format_decimal(v)` == `format(v, "f")` across edge cases (`-0`, `0E-8`,
  trailing zeros) before editing.
- Delegated `_actions_common._display_decimal` and `_decimal_to_string` to
  `core.decimal.format_decimal`; kept the helper names so importers
  (`_actions_manual`, `_review_projection`) are unaffected.

## Outcome

Committed as `0cc2af263`, tagged `relocation:format_decimal`. Ruff clean; 296
ledger tests pass.

## Notes

Two `test_llm_vision_evidence.py` tests fail with
`_classify_with_evidence() missing kwarg 'vision_model'` — unrelated peer churn
in the actively-developed LLM-vision surface (`_llm_classification.py`, which
A3 does not touch; 0 references in the changed file). Recorded as peer-owned
per full-tree-gate-must-distinguish-owner; not in this campaign's scope.
