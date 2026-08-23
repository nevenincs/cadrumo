---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:923cd2fb93ed4623fc9f4d7bda4d4cdc6040f73014d26ac8c78ca03b78150489'
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
