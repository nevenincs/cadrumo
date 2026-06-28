---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S18'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# emit a diagnostic for an unresolved non-formula relation that today produces neither value nor warning at calculate time

## Scope

- `src/aeat/application/calculations/_relation_prefill.py`

## Description

- Identify the silent gap: `unresolved_relation_ids` was filtered to formula-referenced relations, so a declared relation resolving to no value and consumed by no formula produced neither a value nor a diagnostic.
- Scope the advisory to the genuinely-orphaned narrow case: a non-formula relation whose `target_binding` is NOT a declared binding on the revision. Such a relation materialises no slot, so an unresolved value reaches nothing observable.
- Deliberately exclude a non-formula relation whose `target_binding` IS a declared binding: it materialises an observable (absent/zero) slot the engine threads, which is the intended cold-start behaviour for the cross-modelo carries (M200/M202/M100).
- Surface the orphaned set through the existing `_unresolved_relation_diagnostics` builder, appended to the formula-relation diagnostics, as a non-blocking advisory.

## Outcome

An unresolved non-formula relation that materialises no binding slot now surfaces a non-blocking advisory instead of vanishing, while the cross-modelo carry cold-start (non-formula relation with a real target_binding) stays silent as before. The formula-relation unresolved set and the engine blank-cell semantics are unchanged.

## Notes

The first draft fired on every unresolved non-formula relation, which regressed eight M100/M200/M202 fold-in live-calculate tests that assert a cold-start produces zero with no diagnostic. The registry validator forbids an orphaned relation in shipped TOML (every relation's target_binding must be a declared binding), so the narrow guard fires for nothing in shipped data and is a defensive screen against a future or hand-built orphaned relation; the S19 test constructs one via model_copy (bypassing cross-section validation) to exercise it. No silent swallow; the advisory is non-blocking, consistent with the existing unresolved-formula-relation advisory.
