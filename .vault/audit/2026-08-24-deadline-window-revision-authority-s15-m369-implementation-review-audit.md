---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:70da9823c6c19365ce7439742848c273c57871cd36580a069ce30cbc971555b3'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
  - "[[2026-08-24-deadline-window-revision-authority-W02-P04-S15]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `deadline-window-revision-authority` audit: `S15 Modelo 369 implementation review`

## Scope

Review the S15 Modelo 369 deadline corpus repair against the accepted architecture, primary-law deadline semantics, canonical ownership, source fidelity, and focused verification evidence.

## Findings

### m369-s15-review | low | No blocking implementation defect found

The changed registry fragments enumerate the complete existing scheme token sets for filing years 2025 and 2026 under their law-selected revisions: four exterior `EXT-*` quarters, four union quarters, and twelve import months per year. All rows use the natural month following the return period, including exact Saturday and Sunday month ends, consistent with HAC/610/2021 article 3 and AEAT's Modelo 369 exception to non-working-day extension. Physical January 2027 dates remain correctly identified as filing-year 2026 coordinates.

Each added row carries the existing reviewed BOE form/order and AEAT procedure sources, and each existing construct closes over its revision's new members. The public bundled authority constructs cold and projects exactly twenty rows per supported year with canonical owner counts `4/4/12`. Focused schema, construct, coordinate, ownership, and Ruff gates pass. The implementation adds no production code and therefore creates no alternate resolver, selector, parser, cadence map, or downstream deduplication path.

## Recommendations

- Accept S15. Preserve the shared supported-year boundary for any later materialisation beyond filing year 2026.
