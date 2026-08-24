---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:9fe4df7ee68f9fa4e691331e948908c7b1760a1601caa35ef93842d65a1fd3ea'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
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

# `deadline-window-revision-authority` audit: `S40 Modelo 130 deadline corpus`

## Scope

Reviewed Step `W02.P14.S40` against the accepted deadline-window revision-authority
decision, the approved plan, the complete Modelo 130 registry revision, and bundled
official AEAT taxpayer calendars for physical presentation years 2022 through 2026.
The review covered the eight-row measured increase, all twenty resulting coordinates,
exact dates and payment cutoffs, source and construct closure, canonical revision
ownership, authority projection, the unpublished 2027 payment boundary, and regression
bite.

Vaultspec RAG first located the existing production authorities for revision selection,
period identity, cadence, supported filing years, deadline projection, and filing-window
resolution. A subsequent exact-symbol sweep confirmed `select_revision`, `Period`,
`registry_period_kind`, `ValidatedRegistryAuthority.deadline_windows`, the shared
supported-filing-year catalogue, and `resolve_filing_window` remain the sole relevant
authorities. Changed-file inspection found no selector, resolver, parser, cadence map,
horizon, deadline catalogue, or deduplication code introduced by this step.

## Findings

No critical, high, medium, or low findings remain.

The resulting corpus contains exactly twenty unique semantic coordinates, four quarters
for every supported filing year 2022-2026, and exactly eight more rows than the original
twelve. Every coordinate is canonically owned by revision `2019-y-siguientes`; the
regression exercises both `select_revision` and validated authority projection rather
than recreating selection or deduplicating results locally.

Dates and published bank cutoffs match the bundled taxpayer calendars. Each
following-January row cites its physical presentation-year calendar. Revision and
construct provenance include all five calendar authorities, and the construct closes
over all twenty deadline IDs. The 2026 fourth-quarter statutory close remains grounded
in the official Modelo 130 instructions, while its unsupported 2027 bank cutoff has
been removed. The regression independently asserts census, identity, year equality,
open, close, payment, exact source set, construct closure, canonical owner, and four-row
projection per supported year.

## Recommendations

Accept Step `W02.P14.S40` without follow-up changes. Preserve this source-first,
canonical-authority, and explicit no-redeclaration audit pattern for the remaining
periodic modelos.
