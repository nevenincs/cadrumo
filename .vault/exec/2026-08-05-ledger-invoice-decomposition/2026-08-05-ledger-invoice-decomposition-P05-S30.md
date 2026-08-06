---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:f3e7c7e8c1d66110f95ab9b219aeffa9aaf99b5a17bafbb16e4c192fbaadcdad'
step_id: 'S30'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# Reconcile the duplicated binding-level assertions between the cross-domain scenario and the rated oracle module, keeping one owner for the shared claim

## Scope

- `src/cadrumo/application/aggregation/tests/test_cross_domain_invoice_scenario.py`

## Description

- Verify, assertion by assertion (not inferred from names), that the cross-domain module's standalone Modelo 130 binding test duplicates a claim the rated oracle module (`test_ledger_income_chain_oracle_rated.py`) already makes, and makes more strongly (same ingresos/retenciones equalities, the same two negative guards, plus the taxable-base binding, the grounding marker, the derivation route, and a statutory cross-check the cross-domain test had no opinion on).
- Remove the weaker, duplicated copy from the cross-domain module, leaving the rated oracle module as the sole owner of that claim.
- Keep the Modelo 130 assertions the cross-domain module still genuinely needs (the invoice-identity reconciliation and the two-modelos-one-base check), and record the resulting division of labour in a section comment: per-modelo oracles assert that one modelo receives its published measure and how it got there; the cross-domain module asserts only what no single-modelo test can state, that several modelos' filed values describe one invoice.

## Outcome

Landed as commit `37145c72ab`, "test(aggregation): stop asserting a modelo's own measure in the cross-domain module".

RECONSTRUCTED RECORD. Written on 2026-08-06 from the commit and its diff, not from a contemporaneous account. The Step was checked without a record and is being reconciled under the plan-closure rule; what follows is what the commit demonstrably does, with no verification claimed that cannot be re-run today.

This was flagged as a PROBABLE match before this record existed; confirmed here by reading the diff against the Step's claim rather than the commit subject alone. The commit removes 35 lines of a standalone Modelo 130 binding assertion from the cross-domain module and states plainly that the rated oracle module already makes every one of those assertions, and more. That is exactly "keeping one owner for the shared claim." Mutation-proved after the removal per the commit message: pointing the surviving cross-domain assertion at the credited cash still reddens the module, so the coverage that remains is load-bearing.

## Verification

Verification is re-runnable rather than quoted from the original session:

```
uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_cross_domain_invoice_scenario.py -n 0 -q
```

## Notes

Reconstructed under the plan-closure rule after `vault plan status` reported this Step checked with no execution record. The commit was located by SCOPE FILE, never by step id: a bare `git log --grep=S##` returns commits from other campaigns, because step ids are per-plan and collide across plans. That search returned confident, plausible, entirely wrong matches before the namespace error was caught.
