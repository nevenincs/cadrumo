---
tags:
  - '#audit'
  - '#rental-income-hardening'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-04-29-rental-income-hardening-plan]]"
  - "[[2026-04-29-rental-income-hardening-adr]]"
  - "[[2026-04-29-rental-income-hardening-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-rental-adr]]"
  - "[[2026-05-19-spanish-stem-terminology-authority-adr]]"
---

# `rental-income-hardening` audit: `legacy plan supersession reconciliation`

## Scope

Reconcile the eleven unchecked mission criteria in the April 2026 plan
against the delivered feature, its delivery audit, and the accepted
successor architecture. This audit decides whether those rows describe
current work; it does not re-audit the underlying LIRPF calculations.

## Findings

### legacy-plan-supersession | low | all eleven legacy criteria are resolved

The original delivery summary and PASS audit establish that the per-finca and
per-contract register, legal tier resolver, grandfathering and forfeiture
paths, amortisation and expense ledgers, Anexo C aggregates, error
registration, coverage floor, and quality gates were delivered. The unchecked
rows are therefore a historical checklist-state defect, not open delivery
work.

The original `aeat rental` and rental-specific Anexo C command shape is no
longer an active requirement. The accepted workflow redesign rejects both
shapes and routes source-fact mutation through the app-ledger boundary and
Modelo consumption through bindings. It also rejects compatibility shims and
direct CLI repository access.

The current codebase deliberately uses the accepted Spanish `fincas` stem:
`domain.fincas` retains the factual register, typed aggregate computation,
Ley 12/2023 tier resolution, and multi-year amortisation-cap logic. Registry
parameters and registry-owned observations provide the Modelo 100 authority,
so reopening the old `domain.rental`, root CLI, or casilla-specific provider
would conflict with the current architecture.

## Recommendations

Mark every legacy mission criterion complete with this audit as its evidence.
Do not recreate the rejected root-level rental CLI or the removed
rental-specific Anexo C provider. Any future rental work must target the
accepted `fincas` source-data and registry-binding boundaries.
