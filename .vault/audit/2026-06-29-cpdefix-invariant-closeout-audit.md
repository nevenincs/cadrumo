---
tags:
  - '#audit'
  - '#cpdefix-invariant-closeout'
date: '2026-06-29'
modified: '2026-06-29'
related: []
---

# `cpdefix-invariant-closeout` audit: `CPDEFIX invariant closeout review`

## Scope

This closeout reviewed the IVA compensation invariant regression coverage after the
CPDEFIX campaign split the large carry-forward test module into smaller behavioral
surfaces. The check focused on preserving the non-tautological assertions for Modelo
303 filed observations, Modelo 390 annual-summary cross-checks, relation-prefill
binding materialisation, FIFO carry partitioning, and wallet reconciliation.

## Findings

### cpdefix-invariant-closeout | low | Test split preserved IVA compensation invariant coverage

The original `test_iva_compensation_history.py` mixed carry-forward modelling,
filed-observation parsing, Modelo 390 annual-summary checks, and relation-prefill
binding assertions in one module. The split keeps the shared builders in
`_iva_compensation_history_support.py` and moves the behavior-specific assertions
into dedicated annual-summary, filed-observation, and relation-prefill modules.
The remaining carry-forward module still covers wallet reconciliation, expiry
boundaries, policy refusal, and lot balance validation. No production code changed
in this slice.

## Recommendations

Keep the split modules behavior-scoped. Future IVA compensation fixes should add
new assertions to the module that owns the invariant being protected instead of
re-growing the catch-all history test file.
