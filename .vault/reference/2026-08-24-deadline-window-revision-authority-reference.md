---
tags:
  - '#reference'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b2f2ad09999613b029d0c843105554bc8c2aef9f752c7cf91700521c5bf1e97e'
related:
  - '[[2026-08-24-deadline-window-revision-authority-research]]'
---

# `deadline-window-revision-authority` reference: `deadline selection call graph and defect inventory`

## Summary

The canonical resolver is `select_revision` in
`src/cadrumo/domain/calculations/registry/_temporal.py`; snapshot construction and
deadline ownership use it. `deadline_windows(year)` in `_authority.py` validates and
projects only the law-selected containing revision, preserving every owned qualified row
without downstream deduplication.

Validation is assembled under `domain/calculations/registry/_validate.py`; ownership,
semantic uniqueness, and periodic completeness belong there. The deadline coordinate is
`(modelo, period.filing_year, period.registry_token, typed qualifiers)`, with redundant
window `filing_year` equal to the period year. Following-year filing dates remain in
`opens_on` and `closes_on`. Completeness consumes the temporal-coverage campaign's
canonical supported-filing-year projection rather than adding a parallel deadline
horizon.

Repair inventory: M190/M193 align the redundant year; M210 uses typed `EVENT-N`/`0A`
plazo qualifiers backed by `ResultDisposition` and official tipo-renta codes; M303
retains rows only in the exact owner including the 2024 cutover; M322 and M353 remove
non-owner copies; and the periodic fleet is materialised through the declared supported
horizon from official evidence. Open frontier revisions do not imply unpublished future
dates.

The consumer chain is authority to `DeadlineEngine.compute` to overview, workflow, and
CLI projections. Filing-window lookup uses `resolve_filing_window`; consumers add no
revision selection, local matching, or multiplicity erasure.

Testing has two distinct contracts. Source-fidelity tests assert literal official dates
and provenance because those regulated facts must fail on a wrong value. Architecture
and fleet tests are catalogue-driven and relational, parametrized by canonical modelo
and period axes, so advancing the supported horizon does not require copying years or
counts.

Runtime “today” is a transient reference-date input, not deadline authority. Production
defaults use the injectable `today_madrid()` civil-clock seam; deterministic tests
supply or freeze the reference date. Feature completion requires all attributable
deadline gates green. Whole-repository runs are revision-scoped release observations
whose unrelated peer failures are routed to their owners rather than reclassified as
deadline defects.
