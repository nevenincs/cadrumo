---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:418fd51a465849ac62ee5806f9af8636d648f741df17dc339aa2828fc4620e6b'
step_id: 'S04'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W01.P01.S04

## Outcome

Proved the retención still reaches casilla 06 end to end, **asserting the value and not merely the wiring** as the Step requires, and separately verified the guarantee the code claims around it, because that claim is what makes the hardcoded constant acceptable at all.

## The value gate

`src/cadrumo/domain/renta/tests/test_retenciones_routing_integrity.py` and `src/cadrumo/application/aggregation/tests/test_renta_income_actividad_contract.py` — **16 passed**.

The routing test pins `RENTA_130_RETENCIONES_OUTPUT_CASILLA` to `"06"` and asserts the casilla is present in every real M130 revision rather than a synthetic one. The contract test carries the value assertion plus a synthetic-fixture case proving the cross-check fires when casilla 06 is stale or missing.

## The wiring claim, verified rather than trusted

`_m130_retenciones_backend_inputs` documents that the constant "is validated against every M130 revision by a `CrossDomainSnapshotCheck` registered at snapshot-build time", and that a revision dropping or renumbering the casilla "would fail loudly at snapshot build, before this function ever runs". The whole T-05 remedy rests on that claim, so it was checked rather than read.

A first pass looked like a dormant validator: `check_m130_retenciones_output_casilla` appeared to have no production caller at all. **That reading was wrong.** The registration is an import-time side effect at `_retenciones_routing_integrity.py:75`, which a grep for the constant does not reach — the call site and the symbol are different searches.

Verified by execution instead of inspection:

    before: []
    after : ['check_first_slice_routing', 'check_m130_retenciones_output_casilla']

Importing `cadrumo.domain.renta` registers both checks.

That `before: []` raises the real question, and it is answered too. The registry starts empty, so a snapshot built on an import path that never imported `domain.renta` would run no cross-domain checks at all. `_snapshot.py::_install_cross_domain_snapshot_checks` closes exactly that hole by importing the peer facade **by name** at the start of every snapshot build, deliberately naming the public facade rather than the private check module, so registration no longer depends on a composition root happening to import renta first. The claim holds end to end.
