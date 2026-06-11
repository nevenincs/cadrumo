---
tags: ['#exec', '#ledger-interface-contract']
date: '2026-06-11'
step_id: 'S27'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# W03.P05.S27 Inventory Rows Typed

Scope: close inventory ledger row, opening layer, and movement typing.

## Description

- Add typed payloads for inventory opening-stock layers and period movements.
- Change `InventoryLedgerPayload` nested lists to those payloads.
- Change `InventoryListResult.rows` to typed inventory ledger rows.
- Add constructor coverage for the nested inventory payloads.

## Outcome

Inventory list output now validates without bare row, layer, or movement dictionaries at the CLI schema boundary.

## Notes

No emit-site rewrite was required because the domain ledger JSON dump already matches the strict nested payload shapes.
