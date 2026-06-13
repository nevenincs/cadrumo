---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `per-modelo-aggregation-pipeline`

## Findings

The current aggregation substrate is split and partly pre-redesign.
`application/aggregation/_renta_ledger.py` covers Renta expense rollups, while
registry bindings still include invoice-source bindings and schema support for
bare `invoice`.

Target placement is `src/aeat/application/aggregation` plus registry binding
providers consumed through `app modelo bindings` and `app modelo calculate`.
Binding inputs must use explicit source kinds: `ledger_transaction`,
`purchase_invoice_evidence`, `payable_invoice`, and `collectible_invoice`.

Required migration: remove bare `invoice` as a registry/source binding input.
Modelo-family aggregation should cover retenciones summaries, 347/349
counterpart aggregation, 720 assets aggregation, and later family-specific
pipelines without ad hoc modelo-local implementations.

Reject extending bare `invoice`, creating a new `data` root, modelo-local ad
hoc aggregators, or compatibility shims that preserve bare invoice semantics.
