---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S32'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




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
