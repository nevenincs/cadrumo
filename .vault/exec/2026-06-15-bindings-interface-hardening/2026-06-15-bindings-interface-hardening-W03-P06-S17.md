---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S17'
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
     The S17 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
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
     The unify the three ADR-R2 revision-carry gate copies onto one shared path consumed by the binding-prefill, cross-period clean-state, and relation-prefill callers and ## Scope

- `src/aeat/application/calculations/_binding_prefill.py`
- `src/aeat/application/calculations/_cross_period_clean_state.py`
- `src/aeat/application/calculations/_relation_prefill.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# unify the three ADR-R2 revision-carry gate copies onto one shared path consumed by the binding-prefill, cross-period clean-state, and relation-prefill callers

## Scope

- `src/aeat/application/calculations/_binding_prefill.py`
- `src/aeat/application/calculations/_cross_period_clean_state.py`
- `src/aeat/application/calculations/_relation_prefill.py`

## Description

- Extract one shared ADR-R2 carry gate `revision_carry_outcome` into a new `_revision_carry_gate.py` helper, returning `(diverges, advisory)` from `(stamped_revision_id, source_modelo, source_filing_year, source_period)` — the single law-determined re-confirmation.
- Reduce `_binding_prefill._revision_carry_outcome` to a thin adapter that extracts the source context off the payload's observation and delegates to the shared gate.
- Reduce `_cross_period_clean_state._revision_carry_check` to a thin adapter that maps the shared `(diverges, advisory)` onto its blocker shape (divergence becomes `REGISTRY_REVISION_DIVERGENCE`); drop the now-unused resources import.
- Route `_relation_prefill._gather_observations_for_snapshot` through the shared gate so a divergent-stamp prior is dropped from the relation fold, closing a re-confirmation gap the relation path was missing.

## Outcome

The ADR-R2 carry decision now lives in one function consumed by all three carry-read sites. The two adapters preserve their existing return shapes and semantics; the relation path gains the divergent-stamp drop consistent with the binding-prefill site.

## Notes

The two real prior implementations (binding-prefill and cross-period clean-state) were behaviour-identical and are now unified verbatim. The relation-prefill gather previously discarded the payload stamp entirely and never re-confirmed it; routing it through the shared gate adds the divergent-stamp drop the `carried-observations-stamp-their-revision` rule requires at every carry read. Mesh enrollment and ownership untouched.
