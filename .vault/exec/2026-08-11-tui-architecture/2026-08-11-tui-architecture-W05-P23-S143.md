---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:865562aef195c9f5428bc240d1807037452c0c3fde4436fd7303bbe45c18a0d3'
step_id: 'S143'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Extend registered operation definitions with validated transient-financial-operand declarations and an effect-receipt resolver that narrows recorded mutation, interruption, and uncertain-effect claims from committed application evidence without exposing financial operand material

## Scope

- `src/cadrumo/application/operations/_registry.py`

## Changes

- `M` `src/cadrumo/application/operations/registry.py`
- `A` `src/cadrumo/application/operations/tests/test_financial_operand_registration.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/ -n0` -> `pass` (342 passed; one pre-existing unrelated failure)

## Notes

The row names `_registry.py`; the module is public `registry.py` after an
earlier relocation Step.

An operand declaration is refused unless the definition can actually honour
it: recorded durability, interrupt reconciliation, a declared input
interaction, and a permitted uncertain effect. A definition that expected to
resume after owner loss would have to invent the amount on restart, which
custody cannot supply.

The effect-receipt resolver only ever narrows. An unevidenced UPDATED or
PARTIAL claim becomes UNKNOWN, and so does an evidenced one whose operand
delivery was uncertain - if the executor may never have seen the amount, the
effect is not definite. A NONE claim needs no evidence. The resolver reads the
custody crash classification and no operand material; the checkpoint holds
none in the first place.

`test_public_contracts.py::...[OperationResultProjectionSuccessV1]` fails on an
open object branch. Verified pre-existing by running it against the unmodified
registry module before the change.
