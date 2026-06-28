---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S20'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Registry Source Alias Routing Removal

## Scope

C4 ledger invoice unification reconciliation for `P04.S20`.

## Description

- Removed the retired alias guard from retenciones observation validation; unsupported source kinds now use the canonical unsupported-source diagnostic.
- Removed the alias from the registry binding selector registry and `DataBindingDefinition.source` literal.
- Routed invoice-shaped binding validation through `INVOICE_BINDING_SOURCE_KINDS` instead of the deleted alias.
- Migrated registry tests from alias fixtures to canonical invoice-family sources, or to `manual_input` where the intent was wrong-source rejection.

## Outcome

Registry binding construction and validation no longer depend on the bare `invoice` source-kind.

## Verification

- `uv run --no-sync ruff check ...` on the touched implementation and test files passed.
- Focused aggregation/operator/registry gate passed: 203 tests.
- `test_registry_schema_part1.py` remains uncollectable because peer support split work removed exported support names before collection.
