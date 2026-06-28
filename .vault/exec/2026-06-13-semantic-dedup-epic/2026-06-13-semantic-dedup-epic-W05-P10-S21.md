---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S21'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C2-1 Replace the three private selector-as-dict clones with the canonical selector_as_dict

## Scope

- `src/aeat/domain/calculations/registry/_binding_selector_utils.py`

## Description

- Re-verified at HEAD: three private selector-as-dict clones
  (`_withholding_bindings` `_selector_as_dict`, `_bindings_previous_filing`
  `_selector_as_dict`, `_formula_initial_values` `_binding_selector_as_dict`)
  byte-identical to the canonical `selector_as_dict` in `_binding_selector_utils`.
- Added the aliased canonical import to each (alias preserving the local call
  name, matching the convention in `_bindings`/`_invoice_bindings`/`_ledger_bindings`)
  and deleted the three local defs.
- Removed the now-unused `pydantic.BaseModel` import from `_formula_initial_values`.

## Outcome

Committed as `b88e004c8`, tagged `relocation:selector_as_dict`. Ruff clean on
all three files, registry collect-only clean (2326 tests), 314 focused
binding/selector/withholding/previous_filing/initial_value tests green. No
public shape change.

## Notes

`BaseModel` remained in use in the other two files (selector model classes); only
`_formula_initial_values` lost its sole `BaseModel` user.
