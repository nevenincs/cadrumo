---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:74e00c21ce0542e674637eb22e9973541c310807a09b830720c7f1a94aa1516e'
step_id: 'S11'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# enumerate secure typed repositories and their aggregate grains

## Scope

- `dev/source_connectivity/discovery.py`

## Description

- Parse production Python structurally and identify repository classes using canonical secure-storage mechanisms.
- Retain typed payload declarations, storage mechanism, aggregate key authority, and source locator.
- Exclude tests, package facades, untyped wrappers, and repositories without secure-storage evidence.

## Outcome

The capability census can now enumerate typed encrypted repositories without a hand-maintained domain list. Inventory, assets, amortization, transactions, and every other structurally matching secure repository enter discovery independently of their names.

## Notes

Vaultspec RAG and regex sentinels found no existing general capability discovery authority. Ruff passed, and the live tree produced typed records including `InventoryLedgerRepository`, `AssetsLedgerRepository`, `AmortizacionLedgerRepository`, and `TransactionCatalogueRepository`. Discovery is advisory evidence only and makes no casilla-equivalence claim.
