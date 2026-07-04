---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S32'
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
     The S32 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Test retenciones source observations are period and source kind filtered and ## Scope

- `src/aeat/application/aggregation/test_source_mesh_retenciones.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Test retenciones source observations are period and source kind filtered

## Scope

- `src/aeat/application/aggregation/test_source_mesh_retenciones.py`

## Description

Verified the required test coverage exists at HEAD; this record closes the test step against the realized coverage rather than adding a duplicate file.

- Confirmed `test_retenciones_aggregation_resolver.py` asserts retenciones source observations are period-filtered: the resolver materialises bindings for a `CalculationSourceContext` scoped to a specific filing year and period token (for example Modelo 115 for 2026 1T, Modelo 180/193 for 2024 0A) and excludes out-of-window observations.
- Confirmed the coverage asserts source-kind and scheme filtering: Modelo 111 scheme-filtered bindings materialise only from observations whose scheme matches the binding, and mixed-scheme stores route each observation to its correct binding.
- Confirmed the empty-store guard: a declaring revision with no matching observations fails before a silent zero and surfaces the period in the advisory context.

## Outcome

Retenciones source observations are proven to be period- and source-kind-filtered by the consolidated retenciones resolver test. No new test file was required; the plan's `test_source_mesh_retenciones.py` intent is satisfied by `test_retenciones_aggregation_resolver.py`.

Gate evidence: `test_retenciones_aggregation_resolver.py` green (period-scoped materialisation, scheme filtering, distinct perceptor count, empty-store fail-before-silent-zero); `test_retenciones_empty_store_advisory_guard.py` green.

## Notes

Closed as verified-at-HEAD. The plan named a standalone `test_source_mesh_retenciones.py`; the realized coverage lives in `src/aeat/application/aggregation/tests/test_retenciones_aggregation_resolver.py` and the sibling empty-store advisory guard, co-located with the resolver per the tests-live-under-domain-tests-folders topology.
