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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace bindings-interface-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The emit a diagnostic for an unresolved non-formula relation that today produces neither value nor warning at calculate time and ## Scope

- `src/aeat/application/calculations/_relation_prefill.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
