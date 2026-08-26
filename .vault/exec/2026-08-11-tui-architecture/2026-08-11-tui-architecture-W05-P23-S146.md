---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:50739c5d8a94a11752fb338918d70b38f78f18c83c078efd9b8436a40aa9db2c'
step_id: 'S146'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Implement the sole TuiOperationFinancialOperandDependencyReceiptV1 validator with accepted-authority, protocol-schema, custody-transition, crash, effect, production-composition, non-retention, current-only, no-legacy, and duplicate-authority evidence checks

## Scope

- `src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py`

## Changes

- `A` `src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py -n0` -> `pass`

## Notes

The validator reads the live tree rather than a recorded receipt. A receipt
attests to what was true when it was written and stops being evidence the
moment anything moves, so every check here is derived: the transition table is
driven state by state rather than described, crash classification is exercised
over every state, and the non-retention checks read the real field sets and
signatures.

The duplicate-authority census was proved to bite by planting a second
`advance_custody` in the package and observing the check red, then removing it.

The accepted-authority check searches for the ADR's status heading instead of
indexing a line, so it cannot pass vacuously when the document shifts.

There is no financial-operand ADR; the governing accepted decision is the
`tui-architecture` ADR, and the check asserts that status.
