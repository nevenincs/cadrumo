---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-18-schema-hardening-plan]]"
  - "[[2026-05-18-schema-hardening-research]]"
---

# `schema-hardening` audit: M100 IBAN rectificacion cross-revision drop

## Open issue

Casilla `0687` (IBAN rectificacion) in M100/2020 was renumbered to
`1780` in M100/2021 and persisted with that id through 2022 and
2023. From M100/2024 onwards the casilla is absent entirely. The
schema-hardening research artefact flagged this as the strongest
example of cross-revision deprecation drift: the registry has no
`deprecated` or `replaced_by` pointer linking the dropped casilla
to its surviving counterpart, so a consumer reading a 2023 record
and trying to map it to 2024 has no schema-level information that
the field has gone away.

## Plan A P05 disposition

The Plan A IBAN retrofit applied `data_type = "iban"` to casilla
`0687` (M100/2020 only) and to casilla `1780` (M100/2021 through
M100/2023). M100/2024 and M100/2025 carry no `1780`; only `1790`
(Compensacion entre conyuges IBAN) is retrofitted in those
revisions.

## Out of scope for Plan A

A registry-level cross-revision deprecation mechanism would require:

- A new `replaced_by: CasillaId | None` or
  `deprecated_in: RevisionId | None` slot on `CasillaDefinition`,
  or a separate `[[revisions.X.casilla_lifecycle]]` table that
  records per-casilla transitions across revisions.
- A snapshot-build validator confirming that every casilla
  reachable from an earlier revision but absent from a later
  revision has a lifecycle record.
- A migration path for consumers (filing draft assembly, oracle
  replay) that resolve a casilla id against a snapshot's revision
  coordinate.

This is orthogonal to the schema-hardening atom layer and belongs
in a follow-up feature. Filed here as the documented open issue
for future scope.

## Acceptance

Plan A P05 ships the casilla-level IBAN retrofits for the two
retained casillas (`1780`, `1790`) in M100. The deprecation issue
remains open without blocking Plan A closure.
