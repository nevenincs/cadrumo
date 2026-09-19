---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:c448d17c2ac8578e34d371d4d796c124e7a63afc978b3a280d56f9e3e9419f3c'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S13 handoff consumption channels`

## Scope

Reviewed W02.P04.S13 against the accepted canonical-derivations decision, campaign plan, research, and repository quality constraints. The scoped production surfaces were `_handoffs.py`, the registry facade, and `_relation_prefill.py`; the scoped gates were `test_relation_handoff_inventory.py` and `test_relation_prefill_source_mesh.py`. The required contract is an exact four-channel projection on the canonical consumption index, persisted on each handoff record, with the unresolved relation partition consuming the canonical functions and no retained private proxy.

## Findings

No actionable S13 findings.

`relation_consumption_index` now preserves primary casilla bindings, alternate casilla bindings, formula relation references, and formula binding references as four distinct immutable fields. `relation_consumption_channels` projects those fields in stable order and reports every applicable channel rather than collapsing them to a boolean. `relation_is_consumed` remains the boolean projection of that same public authority. The new projection is exported once through `_handoffs.py` and once through the registry facade; an identity probe confirmed that the facade objects are the canonical implementations.

`RelationHandoffRecord` carries the exact typed channel tuple. `audit_registry_relation_handoffs` constructs one canonical index per revision and derives each record's tuple from the production projection. A real bundled-authority probe produced 78 records with zero empty tuples. It independently confirmed `renta-2025-rel-193-retenciones-anuales` as exactly `alternate_binding` and `renta-2024-rel-130-pagos-fraccionados` as exactly `formula_relation`. The bundled distribution contains 41 primary-binding, 3 alternate-binding, and 34 formula-relation memberships; the fourth formula-binding route remains covered by the canonical S12 function gates rather than fabricated as a bundled S13 example.

The unresolved partition deletes `_formula_relation_ids`, removes the declared-binding membership proxy, and builds its formula-fed, orphaned, and bound partitions from `relation_consumption_index`, `relation_consumption_channels`, and `relation_is_consumed`. Formula consumption includes both direct relation references and formula binding references; bound consumption includes both primary and alternate casilla bindings. Unknown relation ids and known relations with no channel remain orphaned. The existing requirement scoping, taxpayer-filing, period-datability, and IVA-wallet exclusions remain additive constraints rather than replacement authorities.

The changed tests load real bundled revisions and call the production consumption functions. Their direct revision construction exercises the defensive orphan branch without replacing or patching production behavior. No scoped test introduces a fake, stub, mock, patch, monkeypatch, skip, expected-failure marker, private duplicate walker, or mirrored expression traversal.

The unchanged applicability hard-count test in the owning registry module currently fails at `156 != 108`. This is the disclosed shared-registry corpus drift: it does not execute or contradict the S13 channel projection, and the 14 changed-surface nodes pass. It is recorded as a verification boundary, not an S13 finding.

## Verification

- Fresh semantic discovery located the accepted canonical authority and the exact production consumer before symbol-level inspection.
- Changed-surface tests: 14 passed.
- Real bundled handoff probe: 78 records, zero empty channel tuples; named alternate and formula examples exact.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed.
- Facade identity: `relation_consumption_index`, `relation_consumption_channels`, and `relation_is_consumed` resolve to the `_handoffs.py` objects.
- Retired duplicate sweep: no `_formula_relation_ids` definition remains; `_relation_prefill.py` no longer imports `expression_relation_refs` or derives consumption from declared binding ids.
- Prohibited construct scan: no fake, stub, mock, patch, monkeypatch, skip, or expected-failure usage on the changed test surface.
- Broader boundary: the unchanged applicability hard-count node failed only because the current authority yields 156 rows while its stale assertion expects 108.

## Recommendations

No corrective action is required for S13. Reconcile the separate applicability hard-count gate with its owning registry-data change before claiming the entire module green; do not alter it as part of this step.

Verdict: **PASS.** W02.P04.S13 preserves all four canonical consumption channels, records the exact channel tuple on every bundled handoff, and retargets the unresolved partition without compatibility or duplicate authority.
