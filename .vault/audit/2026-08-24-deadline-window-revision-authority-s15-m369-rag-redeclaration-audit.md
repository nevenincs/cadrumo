---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:b8d7f63878fc4f3289307aa55772f36084871c609d3dc6dd77e3ebdb3b3ab618'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# `deadline-window-revision-authority` audit: `S15 Modelo 369 RAG redeclaration audit`

## Scope

Audit S15 for accidental redeclaration of deadline resolution, period/cadence interpretation, revision selection, or legal-source authority before and after the Modelo 369 registry repair.

## Findings

### m369-canonical-authorities | low | Existing authorities cover the complete change

Semantic code search for Modelo 369 OSS/IOSS deadline windows, scheme periods, registry authority, resolver, and cadence located the existing production cluster: `OssIossRegime` defines scheme meaning; the three revision `period_selector` and `filing_schedules` declarations own the scheme-specific token sets; `Period` owns token parsing; `select_revision` owns law-selected revision resolution; `ValidatedRegistryAuthority.deadline_windows` owns public projection; and `resolve_filing_window` owns matching. Semantic vault search located the accepted deadline-window revision-authority ADR, research, and plan governing the change.

Exact-symbol confirmation with `rg` pinned `resolve_filing_window`, `deadline_windows`, `registry_period_kind`, `select_revision`, `EXT-1T`, the three revision IDs, and all existing Modelo 369 tests and data fragments. The nearest complete analogue was the existing Modelo 369 registry test module and its construct-closure assertion. No missing abstraction was found.

Post-change exact diff and symbol review shows only registry rows, membership declarations, and assertions changed. No Python production module, enum, period parser, cadence map, selector, resolver, or source catalogue entry was added or duplicated.

### m369-primary-authority | low | One stable legal rule grounds all supported rows

BOE HAC/610/2021 article 3 requires presentation within the natural month following the end of the return period. Directive 2006/112/EC articles 364, 369f, and 369s establish quarterly exterior/union returns and monthly import returns, due by the end of the following month. AEAT's taxpayer-calendar guidance expressly excludes Modelo 369 from weekend and holiday extensions. These primary sources ground deterministic materialisation for every supported filing year 2022-2026, including physical close dates in January 2027 for 2026 Q4/month 12.

The post-extension exact corpus sweep proves `20` rows for each of 2022, 2023, 2024, 2025, and 2026 (`100` total). Exact-symbol review of the changed M369 surface finds only declarative rows, existing construct memberships, and tests; no function, class, enum, selector, resolver, parser, cadence map, horizon, or source catalogue was introduced.

## Recommendations

- Keep future filing-year materialisation constrained by the shared temporal-coverage authority; the stable month-end rule determines dates but does not itself declare the registry's supported horizon.
- Continue expressing each scheme through its established tokens and revision owner. Do not add a Modelo 369 cadence function or downstream deduplication.
