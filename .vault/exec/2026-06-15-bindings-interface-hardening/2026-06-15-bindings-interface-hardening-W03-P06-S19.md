---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S19'
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
     The S19 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
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
     The add carry-gate parity and relation-diagnostic tests asserting one gate path and a surfaced diagnostic for an unresolved non-formula relation and ## Scope

- `src/aeat/application/calculations/tests/test_carry_gate_parity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add carry-gate parity and relation-diagnostic tests asserting one gate path and a surfaced diagnostic for an unresolved non-formula relation

## Scope

- `src/aeat/application/calculations/tests/test_carry_gate_parity.py`

## Description

- Add a new carry-gate parity test module that exercises the shared gate and both adapters (binding-prefill and cross-period clean-state) on the same input across the four R2 cases — matching, divergent, missing-stamp, indeterminate — and asserts all three report the same `(diverges, advisory)` decision.
- Add a behaviour-preservation test that a divergent stamp still maps to the `REGISTRY_REVISION_DIVERGENCE` blocker at the cross-period site.
- Add two non-formula-relation tests in the relation-prefill test module: a false-fire guard asserting an M202 cold-start non-formula relation (real target_binding, observable slot) is NOT flagged, and an orphaned-relation test asserting an advisory fires for a relation whose target_binding is not a declared binding (built via model_copy to bypass the cross-section validator, which forbids the orphaned shape in shipped TOML).
- Use real registry authority and real law-determined revision ids throughout; no mocks, no hand-computed calc values.

## Outcome

Five carry-gate parity assertions and one non-formula-relation diagnostic test pass. The parity test pins that the three carry sites cannot drift apart, and the relation test proves the S18 silent gap is closed.

## Notes

The tests import the private symbols-under-test (`_revision_carry_outcome`, `_revision_carry_check`, `_ObservationEnvelopePayload`, `_formula_relation_ids`), matching the established pattern in the sibling stamp-roundtrip and binding-prefill test modules; pyright reports these as reportPrivateUsage warnings only, consistent with those existing tests, with zero type errors.
