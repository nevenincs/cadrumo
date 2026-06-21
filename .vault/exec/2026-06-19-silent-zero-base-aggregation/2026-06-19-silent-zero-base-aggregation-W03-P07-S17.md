---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S17'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace silent-zero-base-aggregation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-06-19-silent-zero-base-aggregation-plan placeholders are machine-filled by
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
     The open a research note for the M130 agrarian estimación-objetiva classification axis distinguishing agrarian-objetiva from actividad-directa income before binding casilla 08 and ## Scope

- `.vault/research/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# open a research note for the M130 agrarian estimación-objetiva classification axis distinguishing agrarian-objetiva from actividad-directa income before binding casilla 08

## Scope

- `.vault/research/`

## Description

Opened the research note scoping the M130 agrarian estimación-objetiva income
classification axis (the prerequisite before casilla 08 "Volumen de ingresos del
trimestre" can be ledger-aggregated). The note records why casilla 08 is not a
bounded mirror (the transaction model carries no agrarian-objetiva marker, so
reusing the estimación-directa income aggregator would mis-route income into the
wrong régimen's casilla) and what is needed (a per-transaction activity-régimen
marker set at classification, validated at preflight), after which casilla 08
becomes a bounded mirror.

Artifact: `.vault/research/2026-06-20-silent-zero-base-aggregation-research.md`.

## Outcome

Research note written and indexed; the agrarian axis is now a recorded ADR-scale
prerequisite so no future agent naively reuses the directa income aggregator for
casilla 08. No code change.

## Notes

This Step is a research deliverable, not a code fix; the agrarian aggregation
itself is deferred until the classification axis lands.
