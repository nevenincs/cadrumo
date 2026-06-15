---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S09'
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
     The S09 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
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
     The lift the four detail-record family and previous_filing op/fact invariants to registry-build, routing each through selector_as_dict and preserving the underlying pydantic field error in the diagnostic and ## Scope

- `src/aeat/domain/calculations/registry/_detail_record_bindings.py`
- `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`
- `src/aeat/domain/calculations/registry/_binding_selector_utils.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# lift the four detail-record family and previous_filing op/fact invariants to registry-build, routing each through selector_as_dict and preserving the underlying pydantic field error in the diagnostic

## Scope

- `src/aeat/domain/calculations/registry/_detail_record_bindings.py`
- `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`
- `src/aeat/domain/calculations/registry/_binding_selector_utils.py`

## Description

- Add a build-time `validate_*_binding(binding) -> list[str]` to each of the four detail-record families (`related_party_operation`, `foreign_asset`, `atribucion_member`, `refund_operation`) in `_detail_record_bindings.py`, lifting the resolve-time `row_field`/`rows`/named-`row_field` invariant to build time via the shared `_validate_detail_record_row_field` helper.
- Add `validate_previous_filing_binding` plus `_validate_previous_filing_invariants` in `_bindings_previous_filing.py`, lifting the supported-op set (`sum`, `copy`, `prior_pagos_fraccionados`), the copy single-casilla rule, and the pagos-fraccionados casilla-pair rule to build time.
- Fix the raw-selector inconsistency: the four detail-record `_validated_*_selector` helpers now `model_validate` through `selector_as_dict` (the normalised mapping the gate sees) instead of the raw `binding.selector`.
- Route each new family validator through `selector_against_model` then `invariant_diagnostics` so the underlying pydantic field error is preserved in the diagnostic.

## Outcome

The four detail-record families and `previous_filing`, whose op/fact invariants previously ran only at resolve time, now reject a malformed binding at registry-build. The resolve-time `_validated_*_selector` / `_aggregate_previous_filing_binding` helpers remain as defence-in-depth re-checks. `test_bindings_previous_filing.py`, `test_detail_record_observations.py`, and `test_detail_record_row_builders.py` pass.

## Notes

Selector normalisation through `selector_as_dict` is now consistent across every family (the detail-record families previously validated the raw selector, which could differ from the gate's normalised view). Committed in `refactor(registry): one binding validator contract (W02.P03)`.
