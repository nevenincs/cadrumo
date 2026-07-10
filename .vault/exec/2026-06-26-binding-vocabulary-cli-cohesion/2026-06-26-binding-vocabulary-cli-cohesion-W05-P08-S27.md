---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S27'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# DEFERRED FOLLOW-UP verification: when F8 lands, run pytest --collect-only -q clean, test_schema_hygiene.py and the bindings-framework gate suite green, and assert the selector union is behaviour-preserving over the prior validate-time selector models

## Scope

- `if F8 is deferred to a separate phase`
- `leave this Wave open and record the carve in the close note`
- `src/aeat/domain/calculations/registry/tests/test_schema_hygiene.py`
- `src/aeat/domain/calculations/registry/tests`

## Description

- Confirm the F8 implementation (`S25` selector discriminated-union, `S26` typed_enum) is landed at HEAD and its blocker cleared: commit `71367c6b9d` enrolled `DONATIVO_DONOR` in the selector-shape expected set, and the previously non-authored `test_selector_shape.py` WIP is now committed and clean.
- Run `pytest --collect-only -q` over the registry test surface; observe clean collection.
- Run `test_schema_hygiene.py` and `test_selector_shape.py`; observe green.
- Run the bindings-framework gate suite over the registry tests; observe green.

## Outcome

F8 verification passes. `test_schema_hygiene.py` + `test_selector_shape.py` are green (50 passed), and the registry bindings-framework gate suite is green (469 passed, 0 failed). The selector discriminated union hydrates every live `BindingSourceKind` selector family — including the `DONATIVO_DONOR` source that previously outran the expected set — and `typed_enum` hydrates to `BindingTypedEnumKind`, behaviour-preserving over the prior validate-time selector models. Collect-only over the registry test surface is clean.

## Notes

S27 was the deferred F8 verification carry-forward. Its two blockers named in the campaign audit — non-authored WIP on `test_selector_shape.py` and the un-currentized `DONATIVO_DONOR` expected set — both cleared via peer commit `71367c6b9d`. No production code was modified in this Step; it is verification-only.
