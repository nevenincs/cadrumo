---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S17'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---




# Run the full bindings test surface and both parity halves and owner-triage the full tree

## Scope

- `src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`

## Description


P04 is a verification-only Step (no production edit). Ran the full bindings test
surface and both parity halves against HEAD and owner-triaged the full tree.

- Both parity halves green: the domain enum-registry gate
  (`test_binding_source_kind_taxonomy.py`) and the application enum-mesh gate
  (`test_binding_source_kind_mesh_parity.py`).
- Full bindings surface green: registry, aggregation, calculations, modelo, and
  invoices test dirs — 3353 + 1042 tests passed across two runs.
- `pytest --collect-only -q src/aeat` collects cleanly.

## Outcome

P04 complete; phase-2.1 taxonomy unification is structurally done.
`BindingSourceKind` is the single source-kind authority across the registry and
the mesh; the two duplicate enums are gone; the counterpart subset is derived; the
two-half parity gate reads the live mesh sets so a future drift fails CI.
Behaviour-preserving throughout — no casilla value shifted.

The enum-mesh gate deliberately reads the LIVE owned/deferred mesh sets (it does
not hard-code any source's disposition), so r2's in-flight withholding enrollment
(moving `withholding` from deferred to owned) will be reflected automatically once
it lands, without a gate edit.

## Notes


Owner-triaged full-tree failure recorded, NOT fixed (per full-tree-gate-must-
distinguish-owner): the docstring-core-struct gate fails on
`aeat.application.aggregation._withholding_source` — an untracked r2 withholding
module missing a `:class:`ModeloRevision`` docstring link. Outside this feature's
surface; r2 owns the fix.

Declined cross-feature ask: a request to land r2's withholding resolver enrollment
(remove WITHHOLDING from DEFERRED, wire the resolver into the calculate mesh) was
attempted but backed out cleanly — it is entangled with r2's live uncommitted
`aggregation/__init__.py` re-export WIP (the package re-export the enrollment
import depends on is not yet committed at HEAD, so an own-only enrollment commit
would either sweep peer WIP or reference a symbol absent at HEAD). r2 is mid-edit
on those exact files and should complete the enrollment. My phase-2.1 enrollment
edits were fully reverted; `_source_mesh.py` is clean and `aggregation/__init__.py`
carries only peer WIP.
