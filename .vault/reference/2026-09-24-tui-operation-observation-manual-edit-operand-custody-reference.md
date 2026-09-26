---
tags:
  - '#reference'
  - '#tui-operation-observation'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:6e2d870ff9b49e58b533bf62f1bf985e14f91b3764ca67652e761cce5f00e823'
related:
  - "[[2026-08-24-tui-operation-observation-adr]]"
---

# `tui-operation-observation` reference: `manual edit values and the transient operand protocol`

How a manual Modelo edit amount reaches its operation today, how that compares
with the accepted operand-custody design, and what exists to support either
path. Read at `tui/modelo` on 2026-09-24.

## Summary

- **The operand declaration is used for bounds only.**
  `_MODELO_EDIT_MANUAL_OVERRIDE_OPERAND`
  (`src/cadrumo/application/modelo/operation_definitions.py:1425`) declares the
  manual-override operand's currency, scale and range. It is attached to no
  definition, and its only use is the submission's bounds check (`:1631`).
- **The amount rides in the request.** The submission validator's docstring
  (`operation_definitions.py:~1998`) says the manual-override amount arrives
  through the admitted scalar intent value, inside the request, because the
  broker path was not reachable from an executor. That reachability claim is
  stale: `OperationExecutorContext.financial_operand`
  (`src/cadrumo/application/operations/owner.py:224`) has existed since
  `bd673aef67` (2026-08-28).
- **Storage policy history.** Before `01b78c1021` (2026-09-22) the edit-apply
  request was credential-free and journalled as plain JSON, with the operand
  declared on the definition. That commit moved the request to secure-reference
  storage (`operation_definitions.py:~2187`) and removed the declaration.
  `src/cadrumo/application/modelo/tests/test_lifecycle_operation_conformance.py:185`
  pins secure-reference storage for edit-apply. The commit message gives no
  rationale.
- **The protocol is implemented and exercised.** The declaration model is
  `src/cadrumo/application/operations/financial_operand.py`, custody states
  are in `financial_operand_custody.py`, and the submission and executor access
  are in `financial_operand_submission.py`. The filesystem custody store is
  `src/cadrumo/adapters/persistence/operations/financial_operand_custody.py`.
  An executor reaching the broker end to end is exercised in
  `src/cadrumo/adapters/persistence/operations/tests/test_financial_operand_executor_custody.py`.
- **No production consumer remains.** No production definition declares a
  transient financial operand. The composition guard that refuses a declaring
  registry without custody is now proven over a test-only declaring definition
  (`src/cadrumo/entrypoints/tests/test_operation_composition.py`).
