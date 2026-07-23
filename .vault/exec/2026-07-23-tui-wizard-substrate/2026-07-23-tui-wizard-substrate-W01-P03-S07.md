---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S07'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Implement the immutable FlowState and the pure transition engine (answer, next, back, jump, reset, restart) with per-transition visibility recompute and staleness marking and ## Scope

- `src/cadrumo/application/flows/_engine.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement the immutable FlowState and the pure transition engine (answer, next, back, jump, reset, restart) with per-transition visibility recompute and staleness marking

## Scope

- `src/cadrumo/application/flows/_engine.py`

## Description

- Implement the immutable FlowState and pure transitions (answer, next, back, jump, reset, restart, set_instance_count) with per-transition visibility recompute, gating-change staleness, repeating-group instance keying and shrink-orphan staleness, and section-exit blocking.
- Land in commit 91c5e51afc; immutability convention documented in 9b03c2180d.

## Outcome

Engine is the single flow authority; frontends dispatch transitions only (reviewer invariant 1 PASS).

## Notes

Stale marks never delete answers; deferral never resolves silently (reviewer invariant 2 PASS).
