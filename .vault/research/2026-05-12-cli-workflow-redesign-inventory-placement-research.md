---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `inventory-placement-and-execution`

## Findings

The root contract has drifted. Current root registration still exposes
`config`, `archive`, `topic`, `help`, and `app`, while the target design permits
only `aeat config` and `aeat app`. Inventory currently lives under
`src/aeat/entrypoints/cli/data/ledgers/inventory.py` and self-identifies as
`aeat data ledgers inventory`.

The older 2026-04-30 inventory CLI ADR selected `aeat data ledgers ...`, but
the apex now forbids a `data` root. The older decision remains historically
useful for command verbs and hardening requirements, but the placement must be
superseded for the CLI workflow redesign.

Inventory is operational ledger evidence, not configuration. The target
placement is `aeat app ledger inventory`, not `aeat config`, `aeat data`, or
`aeat app modelo`. Modelo workflows may consume inventory-derived readiness,
but mutating inventory commands belong with ledger evidence.

The retained command shape is:

```text
aeat app ledger inventory list [--format json|text]
aeat app ledger inventory create ACTIVIDAD --year YEAR --valuation-method METHOD [--opening-stock AMOUNT] [--format json|text]
aeat app ledger inventory movement add --actividad ID --year YEAR --movement-id ID --date DATE --kind KIND --quantity QTY [--unit-cost AMOUNT] [--taxable-base AMOUNT] [--vat-rate RATE] [--format json|text]
aeat app ledger inventory valuation preview --actividad ID --year YEAR [--format json|text]
```

Reject keeping `aeat data ledgers`, adding a third `data` root, preserving
hidden compatibility shims, moving inventory under `config`, or moving mutating
inventory under `app modelo`.
