---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S11'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-user-docs-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden filing-periods.md and ## Scope

- `docs/how-to/filing-periods.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden filing-periods.md

## Scope

- `docs/how-to/filing-periods.md`

## Description

- Verify-close: read `filing-periods.md` against its 2026-06-18-audit finding m10 and confirm resolution at HEAD.
- Confirm m10 (`0A` listed as a common token while a 303-scoped rejection lists only `1T`-`4T`/`01`-`12`): the page now states explicitly that "which tokens a modelo accepts is modelo-specific, not universal" - a quarterly modelo like 130 accepts only `1T`-`4T`; an annual modelo like 390 accepts only `0A`; Modelo 303 accepts `1T`-`4T` and `01`-`12` but NOT `0A` - and points to `aeat app modelo describe` to read a modelo's `Períodos` line.
- Confirm the calendar-shape rejections (`2026Q1`, bare `2026`) are documented with the `--year` + `--period` fix.

## Outcome

- Page verified compliant at HEAD; finding m10 resolved. Delta: none required. CLI conformance gate green.

## Notes

- The period-token grammar is grounded in the single Period boundary authority. AEAT tokens documented precisely.
