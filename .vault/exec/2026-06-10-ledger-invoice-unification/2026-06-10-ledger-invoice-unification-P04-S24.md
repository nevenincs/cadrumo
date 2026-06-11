---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
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

## Outcome

The full `src/aeat` collect-only gate is still blocked by unrelated peer support-module split errors. The C4 alias-retirement surface is covered by focused green lint, aggregation/operator/registry tests, API-stub drift, and CLI conformance gates.

## Verification

- `uv run --no-sync pytest --collect-only -q src/aeat` collected 14,545 selected tests and stopped with 26 collection errors.
- Failure signatures include missing support exports from declaracion parser support, AEAT auth/sede support, secure-object support, ledger action support, modelo file-flow support, registry referential/schema support, `_validate_semantic_roles`, and `LedgerPeriodPayload`.
- `test_registry_schema_part1.py` specifically still fails collection before execution because `CasillaContinuidadEvolutionDefinition` is not exported from `_registry_schema_support`.
