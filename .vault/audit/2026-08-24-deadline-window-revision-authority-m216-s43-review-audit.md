---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:2637813992bd5c9b085a493414f3663ddf1581e091da6950be7422c89a1390c2'
related: []
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

# `deadline-window-revision-authority` audit: `m216 s43 review`

## Scope

Independent read-only review of `W02.P14.S43`: the Modelo 216 revision,
deadline-window, construct, and focused-test changes were checked against the
accepted deadline-window authority decision, the measured campaign census, and
the bundled AEAT 2024-2026 calendar corpus. Discovery began with Vaultspec RAG
and was narrowed by exact-symbol searches for the canonical revision selector,
period classifier, authority projection, and all changed M216 declarations.

## Findings

No findings. The reviewed change adds exactly the four previously absent
coordinates, `2024 1T` through `2024 4T`; the resulting supported M216 census is
exactly twelve coordinates for 2024-2026 and contains no 2022 or 2023 row.

The bundled AEAT calendars directly support every materialised value. The 2024
calendar publishes closes on 22 April, 22 July, and 21 October with payment
cutoffs on 17 April, 17 July, and 16 October, while its 2025 physical-calendar
fourth-quarter close and cutoff are 20 and 15 January. The 2025 calendar supports
the corrected 21 April and 21 July weekend dates and the 15/16/15 payment
cutoffs; the 2026 calendar supports the remaining published dates and cutoffs.
The `2026 4T` window closes physically in 2027 and correctly has no unsupported
`payment_cutoff_on`.

Revision, construct, and window source references close over the three reviewed
calendar sources, whose catalogue records resolve to bundled files with AEAT
`official_source_guidance` authority. Every window resolves to revision
`2024-y-siguientes` through the existing `select_revision`; period assertions
reuse `registry_period_kind` and `PeriodKind`. Vaultspec RAG located those
canonical symbols in `_temporal.py`, `_validate_revision_rules.py`, and
`_authority.py`, and exact diff/symbol confirmation found no new selector,
resolver, parser, cadence authority, filing-year horizon, deadline catalogue,
enum, class, or production helper. The only new mapping is the test's exact
expected census, not runtime authority.

Focused verification passed: all six Modelo 216 registry tests and Ruff checks
for the changed test module are green. The exact-census test compares complete
coordinates and dates; the companion test proves canonical ownership, cadence,
source resolution, source corpus presence, and the deliberate absence of the
unsupported 2027 cutoff.

## Recommendations

Approve `W02.P14.S43` as implemented. No follow-up correction is required.
