---
tags:
  - '#exec'
  - '#session-honest-followups'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S14'
related:
  - "[[2026-06-02-session-honest-followups-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace session-honest-followups with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-06-02-session-honest-followups-plan placeholders are machine-filled by
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
     The Diagnose xdist collection-skew root cause and add deterministic test discovery gate and ## Scope

- `pyproject.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Diagnose xdist collection-skew root cause and add deterministic test discovery gate

## Scope

- `pyproject.toml`

## Description

- Backfill the missing execution record for checked Step `P03.S14`.
- Recover diagnostic evidence from commit `660f8486c1`.
- Record that xdist collection skew was handled operationally through the existing `aeat-local-execution` sequential-rerun mandate, while a deterministic discovery gate was left out of session.

## Outcome

- `P03.S14` has a canonical exec record linked to the parent plan.
- The historical closure is a documented operational disposition, not a new `pyproject.toml` gate implementation.
- No source files were changed by this backfill.

## Notes

- This is intentionally recorded as non-implementation closure evidence.
