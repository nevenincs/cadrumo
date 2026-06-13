---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `domain harvest rental`

## Topic

Harvest the existing rental domain into the CLI workflow redesign.

## Audit Surface

The audit covered the apex CLI workflow redesign ADR §5.2 and §8, the
2026-04-29 rental-income-hardening ADR, modelo-work-units,
app-modelo-bindings, ledger ADRs, current `domain/rental`, and the Modelo 100
binding path.

## Rewrite Scope

This research supports a child ADR that decides the application wrapper API,
CLI placement for rental/finca register, Modelo 100 binding path, art. 22-24
tier exposure, storage/event contract, rejected shapes, and no-shim rule.

## Findings

The rental domain has real backend capability but is not productized through an
application wrapper or CLI surface.

Apex states Modelo 100 is calculation-ready, but rental aggregation remains a
backend gap: there is no application wrapper and the Modelo 100 rental binding
path is incomplete.

The domain rental layer currently exposes records, repositories, aggregate
calculation, tier resolution, expense rollup, and amortization directly. There
is no `aeat.application.rental` package and no rental CLI.

The current Modelo 100 binding path only covers first-slice Renta ledger
expense aggregation through declaration-era `_aggregate_filing_inputs`.
Registry support is limited to `ledger_renta_expense_aggregation`. Rental
register output must use a new binding source/provider,
`rental_register_aggregation`, rather than overloading the existing ledger
expense aggregation path.

The existing rental SQL tables are not bucket-linked. The bucket ADR requires
app records and events to be bucket-linked.

## Product Shape

Add `aeat.application.rental` before exposing CLI behavior.

The wrapper should own:

- `list/get/create/update/dispose finca`
- `list/create/update/terminate contracts`
- `record/list income`
- `record/list expense`
- `recompute_amortization`
- `compute_rental_aggregates_for_year`
- `resolve/preview_modelo100_rental_bindings`

Rental register mutation and inspection belong under:

- `aeat app ledger rental finca ...`
- `aeat app ledger rental contract ...`
- `aeat app ledger rental income ...`
- `aeat app ledger rental expense ...`
- `aeat app ledger rental amortization ...`

Modelo 100 readiness belongs under:

- `aeat app modelo bindings list --modelo 100 --year YYYY --period 0A`
- `aeat app modelo bindings preview --modelo 100 --year YYYY --period 0A`

Calculation consumes bindings through `aeat app modelo calculate`.

## Tier Exposure

Article 22-24 tiers are derived by domain/application output. The CLI collects
source facts only, then exposes tier explanation, readiness, and missing facts.
Users do not select art. 23.2 tier flags.

## Events

Application mutations emit:

- `rental.finca.created`
- `rental.finca.updated`
- `rental.finca.disposed`
- `rental.contract.created`
- `rental.contract.updated`
- `rental.contract.terminated`
- `rental.income.recorded`
- `rental.expense.recorded`
- `rental.amortization.recomputed`

Binding preview is read-only and emits no event. Calculation events are
modelo-owned.

## Rejected Shapes

Reject:

- root `aeat rental ...`
- rental-specific `anexo-c`
- direct CLI calls to domain repositories
- old shims
- hidden declaration aggregate reuse
- user-selected art. 23.2 tier flags
