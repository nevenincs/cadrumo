---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S08'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# define one validate(binding)->list[str] validator per source family registered in the single binding dispatch table alongside the selector model

## Scope

- `src/aeat/domain/calculations/registry/_bindings.py`

## Description

- Define one `_BindingFamilyValidator` type alias (`Callable[[DataBindingDefinition], list[str]]`) and one `_BINDING_VALIDATOR_REGISTRY` dispatch map in `_bindings.py`, keyed by `BindingSourceKind`, with exactly one accumulating `validate(binding) -> list[str]` validator per source family.
- Rewrite `validate_binding_selector_shape` to route every binding through the single table entry for its source, replacing the prior split between the selector-shape registry, the withholding `list[str]` special case, and the inline counterpart-invariant branch.
- Add shared `selector_against_model` and `invariant_diagnostics` helpers in `_binding_selector_utils.py` so every family validator validates the selector shape and lifts its op/fact invariants while preserving the underlying pydantic field error verbatim (no flattening to a generic message).
- Add a `_validate_selector_only` factory for the families with no op/fact invariant beyond the strict selector model (`manual_input`, `profile`, `relation_prefill`).

## Outcome

The three incompatible validator conventions (raising `validate_*`, the withholding `list[str]` accumulator, and the no-public-validator detail-record families) now conform to one `validate(binding) -> list[str]` signature behind a single dispatch table. `test_selector_shape.py` and the new build-validation tests pass; the dispatch table covers all seventeen source tokens.

## Notes

The two `test_selector_shape.py` cases that pinned the looser single-entry-point behaviour for `collectible_invoice` (`base_sum` + `grouping`, and the `counterpart invariants` label) were updated to the unified contract: invoice-shaped sources now run the strict invoice validator, and a true counterpart-only source (`ledger_transaction`) carries the counterpart label. Committed as part of `refactor(registry): one binding validator contract (W02.P03)`.
