---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S30'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S30 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Enroll retenciones aggregation through repository backed source resolution and ## Scope

- `src/aeat/application/aggregation/_retenciones.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Enroll retenciones aggregation through repository backed source resolution

## Scope

- `src/aeat/application/aggregation/_retenciones.py`

## Description

Verified the step is already implemented at HEAD by prior source-mesh work; this record closes it against real gate evidence rather than re-implementing.

- Confirmed `RetencionesAggregationSourceResolver` is enrolled in the live `merge_source_resolutions` mesh tuple on the calculate path, reading the dedicated per-perceptor retención observations store through its repository rather than a synthetic in-memory source.
- Confirmed the resolver materialises the retenciones family bindings from real persisted observations: Modelo 115 quarterly count and base, and Modelo 180 / 193 distinct perceptor-NIF counts, scheme-filtered where the binding declares a scheme.
- Confirmed an empty retenciones store on a declaring revision surfaces a no-silent advisory and still materialises an explicit zero rather than a silent blank, honouring the no-dormant-source-resolvers and no-silent-under-declaration rules.

## Outcome

Retenciones aggregation is enrolled through repository-backed source resolution on the live mesh. No production code change was required; the step was already satisfied at HEAD.

Gate evidence: `test_retenciones_aggregation_resolver.py` green (real-store distinct perceptor count, Modelo 115 count and base, Modelo 111 scheme-filtered bindings, empty-store fail-before-silent-zero); `test_retenciones_empty_store_advisory_guard.py` green; the reflective enrollment gate `test_source_resolver_enrollment.py` green.

## Notes

Closed as verified-at-HEAD. The resolver lives in `src/aeat/application/aggregation/_retenciones.py` and is enrolled from the mesh builder in `src/aeat/application/modelo/_calculation_actions.py`.
