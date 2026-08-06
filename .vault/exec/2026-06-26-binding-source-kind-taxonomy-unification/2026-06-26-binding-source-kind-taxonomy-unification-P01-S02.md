---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:515aa8a5fcc2117a4f957d213f4c856cd42eca50b3bafae656c862049d541c18'
step_id: 'S02'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---

# Extend the source-kind parity gate with an enum-to-mesh half and decide the purchase_invoice_evidence and ledger_transaction disposition

## Scope

- `src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`

## Description

- Reconcile `P01.S02` as the parity-gate half of the atomic P01 landing.
- Record that `a99a8cac0b` / `b869dcda4a` extended the registry parity gate,
  assigned explicit dispositions for the reserved invoice and ledger tokens, and
  added the application mesh-parity sibling gate while adding the mesh-only
  members.
- Preserve the layer split: the domain registry gate stays in
  `test_binding_source_kind_taxonomy.py`; the application mesh gate stays in
  `test_binding_source_kind_mesh_parity.py`.

## Outcome

The checked row now has its own exec record. The existing P01 evidence already
recorded both parity halves green, 26 combined parity / boundary / enrollment
tests green, and clean `src/aeat` collection for the atomic landing.

## Notes

No code changed in this reconciliation. This record closes the missing exec
record for an already-checked step.
