---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S09'
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
     The S09 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Cover complete navigation scenarios (back, jump, gating-answer change marks dependents stale, reset, restart, repeating-group instances, deferral) with engine transition tests and ## Scope

- `src/cadrumo/application/flows/tests/test_engine.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Cover complete navigation scenarios (back, jump, gating-answer change marks dependents stale, reset, restart, repeating-group instances, deferral) with engine transition tests

## Scope

- `src/cadrumo/application/flows/tests/test_engine.py`

## Description

- Author the engine transition suite covering navigation, canonicalisation, staleness, reset, restart, repeating groups, deferral, section-exit blocking, and the submit gate.
- Land in commit 30e5884352 (18 tests).

## Outcome

All 18 green; a real cross-field validator registered through the public registry exercises the section-exit gate.

## Notes

Authored by the dispatched high-executor.
