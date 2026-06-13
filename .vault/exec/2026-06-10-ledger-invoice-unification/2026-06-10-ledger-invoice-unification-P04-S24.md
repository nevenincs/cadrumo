---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S24'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Full Collect-Only Gate

## Scope

C4 ledger invoice unification reconciliation for `P04.S24`.

## Description

- Ran the exact full-tree collect-only gate requested by the plan.
- Captured the current failure signature and left the plan step open because the gate is not green.
- Repaired peer split-test support exports that were blocking full collection.
- Reran the exact full-tree collect-only gate and closed the plan step after the gate passed.

## Outcome

The full `src/aeat` collect-only gate is green after reconciling the support-module split exports. The C4 alias-retirement surface is covered by the focused green lint and the full collection gate required by `P04.S24`.

## Verification

- `uv run --no-sync pytest --collect-only -q src/aeat` collected 14,545 selected tests and stopped with 26 collection errors.
- Failure signatures include missing support exports from declaracion parser support, AEAT auth/sede support, secure-object support, ledger action support, modelo file-flow support, registry referential/schema support, `_validate_semantic_roles`, and `LedgerPeriodPayload`.
- `test_registry_schema_part1.py` specifically still fails collection before execution because `CasillaContinuidadEvolutionDefinition` is not exported from `_registry_schema_support`.
- Rerun on 2026-06-11 after peer churn settled further collected 14,689 selected tests and stopped with 20 collection errors. Remaining signatures are still support-module export splits: declaracion verification-chain support, AEAT auth support, secure-object support, runtime migrated repository support, ledger action support, modelo file-flow support, registry referential/schema support, `_validate_semantic_roles`, and `LedgerPeriodPayload`.
- Final rerun on 2026-06-11: `uv run --no-sync pytest --collect-only -q src/aeat` collected `15101/16882` tests with `1781 deselected` and exited 0.
- Focused support reconciliation guard: `uv run --no-sync pytest --collect-only -q` across the previously failing split test files collected `582` tests and exited 0.
- Focused lint guard: `uv run --no-sync ruff check` across the touched support and payload modules exited 0.

## Notes

- `vaultspec-core vault plan step check .vault/plan/2026-06-10-ledger-invoice-unification-plan.md S24` marked the step closed, then exited 1 in cache invalidation because the vault context variable was unset. The plan row was verified closed after the command.
