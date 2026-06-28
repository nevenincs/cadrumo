---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S07'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-fold-in-carry-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-high-executor: route the previous_filing observation-fold path through the one helper, removing the third duplicate loop (apply-cached on collision, peer-WIP likely) and ## Scope

- `src/aeat/application/calculations/_binding_prefill.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-high-executor: route the previous_filing observation-fold path through the one helper, removing the third duplicate loop (apply-cached on collision, peer-WIP likely)

## Scope

- `src/aeat/application/calculations/_binding_prefill.py`

## Description

- Extract the trivial sum/copy fold arithmetic, implemented once in the relation fold helper and again in the previous_filing aggregator, into one shared `fold_sum_or_copy` primitive in `_observation_fold.py`, parameterised by the caller's diagnostic subject and copy-unit so each path keeps its exact error vocabulary.
- Route `_aggregate_previous_filing_binding`'s SUM and COPY branches through the shared primitive; the relation `fold_observed_requirement_values` already delegated to it.
- Keep the Modelo 130 `prior_pagos_fraccionados` casilla-05 identity routed locally before any sum/copy delegation.

## Outcome

- One commit `049e7fecd` (`relocation:previous-filing-fold`), 3 files. No casilla value shifts. The full registry plus calculations suites passed (3253 tests, unchanged baseline); the M130 casilla-05 carry, M390 FIFO, M303 refunded-period, and pull-vs-calculate parity gates passed (89 tests); collect-only clean.

## Notes

- Design finding surfaced, not forced: the previous_filing aggregator is NOT a third copy of the two relation fold-twins that S06 collapsed. It has a different gather (walks multiple ordered source casillas per anchor with a per_grupo_member fan-in and an optional-minoracion branch, vs the relation gather's single casilla and one match per period), a typed op taxonomy, and the unique M130 identity. Only the sum/copy arithmetic genuinely overlaps, so that arithmetic is single-sourced while the distinct gather, op-dispatch, and prior_pagos identity stay where they belong. This matches the reference D1 drift note.
