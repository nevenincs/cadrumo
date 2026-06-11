---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
step_id: 'S21'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Operator Source Kind Contract Update

## Scope

C4 ledger invoice unification reconciliation for `P04.S21`.

## Description

- Updated the operator-surface `SourceKind` contract test to require exact equality with `AggregationSourceKind`.
- Removed the previous canonical-minus-`INVOICE` assertion now that the alias is gone.

## Outcome

The operator-facing source-kind taxonomy and core aggregation taxonomy are pinned to exact parity.

## Verification

- `uv run --no-sync pytest -m "integration or not integration" src/aeat/application/operator_surface/tests/test_contract.py -q` was included in the 203-test focused green gate.
- CLI documented-command and JSON schema conformance gate passed: 133 tests.
