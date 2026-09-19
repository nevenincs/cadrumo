---
tags:
  - '#audit'
  - '#rental-income-hardening'
date: '2026-07-12'
modified: '2026-09-08'
body_hash: 'sha256:29d989bf6bc24ace45a0e7190bccd9292a52fec80f888a449f225ac26a36fa47'
related: []
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

### Resolution (2026-09-08)

The audited subsystem was withdrawn. Later source-integration grounding proved that no finca source kind, application workflow, calculation binding, command, or presentation consumer existed; `fincas_source_readiness` could only return false. The domain package, persistence adapter and tables, dormant error vocabulary, and synthetic tests were therefore a disconnected pre-release feature rather than a live rental-income capability. The canonical Modelo 100 registry parameters and official legal corpus remain.
