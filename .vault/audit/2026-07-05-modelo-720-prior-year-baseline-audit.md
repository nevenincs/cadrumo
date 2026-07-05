---
tags:
  - '#audit'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
  - "[[2026-07-05-modelo-720-prior-year-baseline-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace modelo-720-prior-year-baseline with a kebab-case feature tag, e.g. #foo-bar.
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

# `modelo-720-prior-year-baseline` audit: `M720 W02 taxonomy implementation review`

## Scope

Reviewed the W02 Modelo 720 class-code taxonomy implementation after S09-S11:
the typed foreign-asset enum, the central Modelo 720 position-102 code map, the
application row-projection helper, the core obligation tests, the application
row-projection tests, the plan checks, and the feature index.

## Findings

### m720-w02-taxonomy-implementation-review | low | no unresolved W02 taxonomy defects found

The implementation now treats the official Modelo 720 position-102 code set as
`C`/`V`/`I`/`S`/`B`, maps real estate to `B`, gives IIC a distinct typed class
mapped to `I`, and excludes `VIRTUAL_CURRENCY` from Modelo 720 projection. The
core totality test still covers every `ForeignAssetClass` obligation group, and
the application row-projection tests prove real estate and IIC through the live
registry row resolver while virtual currency fails closed.

The remaining open work is not a W02 taxonomy defect: W03 still owns the
row-carrier source-mesh promotion and enrollment of the foreign-asset resolver.

## Recommendations

- Proceed to W03.P04.S12 with the row-carrier ADR before editing source-mesh or
  `_calculation_actions.py`.
- Keep Modelo 721 virtual-currency projection separate; do not add a Modelo 720
  fallback code for `VIRTUAL_CURRENCY`.
