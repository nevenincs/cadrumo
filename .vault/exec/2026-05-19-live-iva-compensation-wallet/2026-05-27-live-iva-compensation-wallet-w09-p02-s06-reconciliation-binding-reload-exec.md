---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-26-modelo-130-relation-regression-plan]]'
  - '[[2026-05-26-modelo-130-relation-regression-adr]]'
---

# W09.P02.S06 Reconciliation Binding Reload

## Scope

Resolved the active reconciliation blocker recorded as `RELOAD-010`.
The blocker was a shared filing-test utility drift: Modelo 130 casilla
15 is a previous-filing bound casilla and cannot be supplied as an
ordinary casilla input without the matching binding source of truth.

## Changes

- Extended the registry-backed filing test helper with an explicit
  `binding_values` channel, preserving the production draft builder's
  registry routing.
- Added a helper guard that rejects duplicate keys between casilla
  values and binding values, so merge order cannot decide source
  authority.
- Removed input-only Modelo 130 casilla 15 fixtures from filing
  reconciliation and helper tests.
- Routed `modelo-130-resultados-negativos-anteriores` and
  `irpf.previous_year_economic_activity_net_income` through binding
  values in the affected tests.
- Replaced non-tax-id profile labels in reconciliation draft fixtures
  with valid synthetic profile identifiers required by the
  `SubjectTaxId` draft boundary.
- Built reconciliation schema providers from each draft's snapshot ref
  so historical-period fixtures do not depend on future current
  revision selection while unrelated registry drift cannot mask the
  reconciliation contract.

## Verification

- `uv run pytest -q src/aeat/application/filing/test_testing_registry.py src/aeat/application/filing/test_calculate.py src/aeat/application/filing/reconciliation/test_reconcile.py`
- Direct provider check for `('200',)`, `('180',)`, and
  `('111', '123', '130')` returned `ok` in the current tree.

## Residual Work

This slice does not change live AEAT read-only acquisition or wallet
authority. The remaining live IVA work stays under `W05`, `W06`,
`W07`, and `W08`: authenticated read diagnostics, read-only guard
hardening, secure-profile acquisition manifests, and multiyear
remote/local reconciliation coverage.
