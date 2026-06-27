---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S03'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---




# Delete the consumer-less ModeloLedgerBindingAggregation model and its test after confirming zero live consumers at HEAD

## Scope

- `src/aeat/application/aggregation/_modelo_bindings.py`

## Description


The consumer-less `ModeloLedgerBindingAggregation` model deletion in
`_modelo_bindings.py` (plus its now-unused import cascade) was prepared via an
apply-cached HEAD-anchored own-only patch that preserved HEAD's empty-store
ADVISORY-return (#35-guard) and excluded the concurrent codex `raise` flip; a peer
commit then landed the identical `_modelo_bindings.py` deletion at HEAD but left the
package re-export and the test consumer dangling (HEAD imported a deleted symbol).
Commit `51828d0ac` completed S03 by removing those two dangling references: the
`ModeloLedgerBindingAggregation` import + `__all__` entry from the aggregation package
re-export, and the `test_modelo_ledger_binding_aggregation_rejects_noncanonical_binding_keys`
validation test (+ its now-unused `ValidationError` import).

## Outcome

P01.S03 complete; the consumer-less `ModeloLedgerBindingAggregation` envelope is fully
retired and the broken HEAD import is fixed. The empty-store ADVISORY-return is
preserved at HEAD. No casilla value shifts.

## Notes


The shared index was volatile this session: an apply-cached staging of
`_modelo_bindings.py` was cleared by a peer commit mid-flight, and the peer landed an
identical class deletion but a PARTIAL one (left the re-export + test dangling). The
campaign absorbed that as an in-scope regression and completed the deletion. The #35
codex `raise` flip remains the peer's uncommitted WIP; it was never carried into any
of my commits.
