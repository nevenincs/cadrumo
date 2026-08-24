---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6ccd7bbd8a5a7319bb144390b1d37b83b82d6ef4b156bdcf4d7c5b6843e56131'
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

# `deadline-window-revision-authority` audit: `S15 Modelo 369 RAG redeclaration audit`

## Scope

Audit S15 for accidental redeclaration of deadline resolution, period/cadence interpretation, revision selection, or legal-source authority before and after the Modelo 369 registry repair.

## Findings

### m369-canonical-authorities | low | Existing authorities cover the complete change

Semantic code search for Modelo 369 OSS/IOSS deadline windows, scheme periods, registry authority, resolver, and cadence located the existing production cluster: `OssIossRegime` defines scheme meaning; the three revision `period_selector` and `filing_schedules` declarations own the scheme-specific token sets; `Period` owns token parsing; `select_revision` owns law-selected revision resolution; `ValidatedRegistryAuthority.deadline_windows` owns public projection; and `resolve_filing_window` owns matching. Semantic vault search located the accepted deadline-window revision-authority ADR, research, and plan governing the change.

Exact-symbol confirmation with `rg` pinned `resolve_filing_window`, `deadline_windows`, `registry_period_kind`, `select_revision`, `EXT-1T`, the three revision IDs, and all existing Modelo 369 tests and data fragments. The nearest complete analogue was the existing Modelo 369 registry test module and its construct-closure assertion. No missing abstraction was found.

Post-change exact diff and symbol review shows only registry rows, membership declarations, and assertions changed. No Python production module, enum, period parser, cadence map, selector, resolver, or source catalogue entry was added or duplicated.

### m369-primary-authority | low | One stable legal rule grounds all supported rows

BOE HAC/610/2021 article 3 requires presentation within the natural month following the end of the return period. Directive 2006/112/EC articles 364, 369f, and 369s establish quarterly exterior/union returns and monthly import returns, due by the end of the following month. AEAT's 2025 and 2026 taxpayer-calendar guidance expressly excludes Modelo 369 from weekend and holiday extensions. These primary sources ground deterministic materialisation through supported filing year 2026, including physical close dates in January 2027 for 2026 Q4/month 12.

## Recommendations

- Keep future filing-year materialisation constrained by the shared temporal-coverage authority; the stable month-end rule determines dates but does not itself declare the registry's supported horizon.
- Continue expressing each scheme through its established tokens and revision owner. Do not add a Modelo 369 cadence function or downstream deduplication.
