---
tags:
  - '#exec'
  - '#iva-compensation-chain'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S03'
related:
  - "[[2026-05-19-iva-compensation-chain-plan]]"
---

# revise Modelo 390 annual compensation reconciliation casillas and bindings

## Scope

- `src/aeat/_data/registry/aeat/modelos/390.toml`

## Description

- Reconciled the historical checked `P01.S03` row to a per-step exec record.
- Anchored the implementation evidence to commit `8173494bf1`, which persisted the IVA compensation-chain execution summary after the source and tests landed.
- Verified at HEAD that the chain plan row remains checked and that `vaultspec-core vault plan status 2026-05-19-iva-compensation-chain-plan --json` reports no missing exec ids.

## Outcome

The row now has a canonical exec record created through `vaultspec-core vault add exec`. This pass changed no source, registry, test, source-kind, resolver convention, validator convention, or plan checkbox state.

## Notes

This is a traceability repair only. The chain plan remains open at `P03.S01` because the linked live IVA wallet plan is still 101 of 102, with `W06.P15.S56` open for operator/live verification evidence.
