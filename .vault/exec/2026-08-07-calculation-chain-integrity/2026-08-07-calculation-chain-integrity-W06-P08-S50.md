---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:bb6a1ac64b41c8933e519136f3039f736b9e2633c5665e94aec4a0b1c9762498'
step_id: 'S50'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S50

## Outcome

Landed: `test_the_intracom_concept_is_still_inside_the_compared_set` in `test_reconciliation_pair_category_parity.py`. The concept is now asserted **by name**, not inferred from a count.

## The hole this closes

The parity gate already guards vacuity with `assert compared > 0`. That is the right global check and the wrong one for this concept, and the distinction is the whole Step.

The comparison runs over the **intersection** of the two sides' `semantic_role` sets. An intersection shrinks silently: if one side stops carrying a role, that role simply stops being compared, while every other role keeps `compared` positive. The gate goes on passing and quietly covers less — no failure, no signal, less coverage.

## Why this role specifically

`iva_cuota_autorepercutida_intracomunitaria` is the concept the entire gate was built from: routing an intra-community services category onto the quarterly line without the annual line gave 84.00 against 63.00 with nothing objecting.

It is also the role most likely to vanish. Splitting an annual casilla per leg — the M390 under-modelling work `S47` scopes — gives the annual side two per-leg roles where the quarterly side carries one combined role. Neither new role intersects the old one, so the concept drops out of the comparison **on the day the split lands**, with nothing reddening.

## Proof it bites

Holds today: 4 passed, so the role is genuinely in the shared set.

Mutation-proved from **outside** the repository, so no tracked file was edited and no window existed in which the repo carried the mutation:

    _INTRACOM_AUTOREPERCUTIDO_ROLE = 'a_role_no_revision_declares'
    -> AssertionError: role 'a_role_no_revision_declares' is compared by no reconciliation pair

So the assertion reddens when the role leaves the shared set, which is exactly the event it exists to catch.

## What the failure message asks for

It does not prescribe a fix, because both fixes are legitimate: carry the combined role on both sides, or teach the gate the per-leg mapping. It forces the choice to be deliberate rather than letting the intersection shrink unnoticed.
