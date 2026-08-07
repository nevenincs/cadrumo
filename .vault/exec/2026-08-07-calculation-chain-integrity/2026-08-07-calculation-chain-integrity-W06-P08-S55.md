---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e4e4ca1643cf0defef49bd17d946e2ed63c70c475c0d3fcf59d359bf9fbfb4d1'
step_id: 'S55'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S55

## Outcome

Landed in code by `75968fd8fa`, verified at HEAD. Recorded here because it had no exec record; the implementation is a peer's.

## What shipped

`_IvaLedgerSelector.applied_rates: tuple[Decimal, ...] | None` (`_ledger_bindings.py:475`), with the matcher gaining the corresponding test:

    if selector.applied_rates is not None and observation.applied_rate not in set(selector.applied_rates):

So a binding may now name the rate values it takes, not only the tier. `None` means the binding is rate-blind and behaves exactly as before, which is what keeps every existing binding working unchanged.

## The axis is opt-in, and that matters

Declared `None` by default rather than defaulting to the full rate set. A binding that says nothing about rates continues to match on tier alone, so this is additive: no shipped binding changes behaviour, and only a binding that opts in becomes rate-specific.

Pinned by `test_iva_rate_value_selector.py` — 3 passed — whose own framing is the reason the axis exists: "a rate-specific binding rejects a same-tier line charged at another rate ... because a tier's rate can change inside a year."

## Interaction with the reachability probe

Worth recording, because the two pieces of `W02.P03` work met here. `applied_rates` carries `min_length=1`, so it cannot be the empty tuple that made `cash_accounting_treatments` produce an unreachable binding. The probe was extended to carry the new axis at the same time (`c155b2aa28`), taking `selector.applied_rates[0]` when populated and `None` otherwise — so a rate-specific selector is still probed against a shape built from its own declarations rather than being silently exempted from the check.
