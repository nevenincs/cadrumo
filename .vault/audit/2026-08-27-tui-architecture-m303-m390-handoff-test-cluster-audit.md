---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:b27d2a66cddf8d1667539c69f95d07127e2fd3ef3f7fa5864f5bb3dd44bed49e'
related: []
---

# `tui-architecture` audit: the M303-to-M390 handoff test cluster

## Scope

The long-open `ModeloAggregationBindingError` in
`application/aggregation/tests/test_invoice_accumulative_cross_modelo_periods.py`
is diagnosed. It is not one stale test: the sibling module
`application/modelo/tests/test_e2e_ledger_m303_quarters_to_m390_annual.py` fails
four tests with the same error family. Five failures across two modules, over the
quarterly-IVA-folds-into-the-annual-return chain, sharing three causes.

No production defect was found. Every refusal below is a guard behaving as
designed; what is stale is the tests' picture of the filing contract.

## Cause 1 -- a caller zero over a source-owned liability (FIXED)

`_reject_caller_overrides_of_source_bindings` refuses caller casilla inputs that
collide with casillas the bucket aggregation owns. The colliding casilla is
**18**, `modelo-303-recargo-equivalencia-super-reducido-cuota`, bound to source
`ledger_iva_aggregation`.

The test supplied it as a manual zero in a "manual resultado casillas" list that
predates the binding. Direction: casilla 18 is a recargo **cuota**, a liability.
A caller zero over a source-derived liability is the under-declaration direction,
which is exactly what the guard exists to refuse. The guard is right.

Fixed in `b5b967cc14` by removing the override. The scenario declares no recargo
supply, so the ledger resolver supplies the same zero.

The binding predates every commit in this campaign; `git log -S` on the binding id
attributes it to earlier registry work.

## Cause 2 -- a Modelo 303 filing needs its resolved result disposition (FIXED)

`require_filing_result_disposition` refuses an M303 filing whose
`result_disposition` is `None`. Its docstring is explicit that this is "a PRESENCE
requirement and never a second derivation", because recomputing it would make a
regulated determination answerable in two places.

The test called `persist_filed_revision_observation` without one. Fixed in
`b5b967cc14` by resolving it through the production
`resolve_modelo_result_disposition` against the seeded profile projected by
`active_taxpayer_profile`, rather than asserting a value in the test.

## Cause 3 -- the annual handoff requires genuinely FILED quarters (OPEN)

With the first two cleared, the test reaches
`M303RegimenSimplificadoAnnualSummaryHandoffError`: "requires the current
calculation pointer to equal the filed revision". The guard additionally requires
the revision to be `PRESENTADO` and to belong to its own work unit.

The test's helper is named `_calculate_and_file_m303_quarter`, but it calculates
and persists observations without performing the filing transition. That
transition is `file_modelo_revision`, which itself requires the revision to be
`VERIFICADO_COMPLETO` first. So satisfying the handoff means driving the real
calculate → verify → file chain for each of four quarters.

Direction: the annual summary REFUSES rather than folding unfiled quarters into
an annual return. That is the conservative direction and harms no taxpayer -- it
is the guard protecting the M390 from being built on quarters that were never
filed.

## Why this was not finished here

Completing cause 3 is not a fixture edit. It means building the verify-and-file
chain across four quarters in a test this campaign does not own, and the same
work is needed in the sibling e2e module. Getting the expectations wrong there
would encode a false picture of a regulated filing transition, which is worse
than a red test that names its own precondition.

The two fixed layers are independently correct and stand on their own. The third
is recorded with its exact guard, its file and line, and the production action
that satisfies it.

## For an owner

Decide whether these five tests should drive the real calculate → verify → file
chain, or whether the M303→M390 handoff deserves a shared test helper that
establishes a filed quarter once. The second is likely, given two modules need
identical scaffolding, and a shared helper would stop the two drifting apart
again.
