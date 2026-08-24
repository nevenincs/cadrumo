---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:54294c212169503f6088613d6d968ab4a0efa57abfdc8036b203897b321b48fb'
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

# `deadline-window-revision-authority` audit: `S38 Modelo 115 deadline corpus`

## Scope

Reviewed Step `W02.P14.S38` against the accepted deadline-window revision-authority
ADR, its research record, the step execution record, and the bundled AEAT taxpayer
calendar catalogues and corpus for physical presentation years 2022 through 2026.
The audit covered all changed Modelo 115 deadline, revision, construct, and regression
test declarations, including source/date/payment fidelity, the exact sixteen-row
increase, applicability preservation, provenance closure, canonical revision ownership,
runtime authority projection, the unpublished 2027 payment boundary, and test bite.

Vaultspec RAG located the existing canonical ownership and projection path through
`select_revision`, deadline semantic coordinates, cadence and supported-year authority,
`ValidatedRegistryAuthority.deadline_windows`, and `resolve_filing_window`. Targeted
exact-symbol and changed-file confirmation found no production selector, resolver,
period parser, cadence authority, supported-year horizon, deadline catalogue, enum, or
parallel code path introduced by this step.

## Findings

No critical, high, medium, or low findings.

The resulting corpus contains exactly twenty unique semantic coordinates, four quarters
for each supported filing year 2022 through 2026, which is the required increase of
sixteen over the original four. Each coordinate remains owned by revision
`2019-y-siguientes`, and the regression exercises both `select_revision` and the
validated authority projection rather than a local deduplication surrogate. The exact
close and payment dates agree with the bundled calendars, including shifted 2024 and
2025 dates. Following-January rows cite their physical presentation-year calendar.
The 2026 fourth-quarter row retains the legally grounded presentation close but no
unpublished 2027 payment cutoff.

The original `pays_rent_with_retencion` applicability predicate is preserved on every
row. Revision and construct source closure include all five calendar authorities, and
the construct references all twenty deadline identifiers. The regression's independent
date oracle asserts row count, identity, tax-year consistency, opening date, close,
payment cutoff, source set, applicability presence, construct closure, canonical owner,
and four-row runtime projection for every supported year; it therefore bites on the
operator-visible multiplicity and omission failures in scope.

## Recommendations

Accept Step `W02.P14.S38` without follow-up changes. Preserve the same source-first,
canonical-authority, and per-modelo RAG redeclaration audit pattern for the remaining
periodic-fleet corpus steps.
