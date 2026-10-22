---
tags:
  - '#adr'
  - '#period-revision-resolution'
date: '2026-08-31'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:3267be7289e38a261518737bd2e195a487a86aba9eb644c6da498e468ae3d59f'
related:
  - "[[2026-06-10-period-revision-resolution-adr]]"
  - '[[2026-06-10-period-revision-resolution-research]]'
---
# `period-revision-resolution` ADR: a non-periodic work target carries no operation-date axis | (**status:** `rejected`)

## Problem Statement

Modelo 308 filing year 2011 spans two record designs. Orden EHA/1033/2011 substitutes
anexo II of Orden EHA/3786/2008 from 1 July 2011, and AEAT publishes the designs as
*"Ejercicios 2009 a 2011-julio"* and *"Ejercicios 2011-julio a 2015"*; the registry
models them as `2009-2011-junio` (`valid_to = 2011-06-30`) and `2011-julio-2015`
(`valid_from = 2011-07-01`). The proposal was to add the operation date as a third
revision-selection axis for 308, on the premise that its period token carried no month.

## Considerations

- The premise is false. The 308 designs print an ordinary period field:
  `aeat-dr-308-2009` admits `1T`-`4T`, and `aeat-dr-308-2011-july` admits `1T`-`4T`,
  `01`-`12` and `0A`. The July boundary falls between `2T` and `3T`.
- `PeriodSelector.period_overrides` already partitions a split year by period, as
  modelo 303 does for 2024.
- `aeat-registry-authority-flow` requires `(modelo, filing_year, period)` to select
  exactly one revision.

## Decision

**Rejected.** No operation-date axis is added. Modelo 308 is addressed by the period
codes its record designs print (`2026-06-01-registry-period-code-union-cli-boundary-adr`
D4). In 2011, `2009-2011-junio` serves `1T` and `2T`, and `2011-julio-2015` serves
`3T`, `4T`, `07`-`12` and `0A`, so the mandated triple selects exactly one revision for
every 2011 coordinate.

## Considered options

**Operation date on the work target.** Rejected: it adds a persisted axis and CLI
input to recover a fact the period code already carries.

**Narrow the year ranges.** Rejected: capping either edition at a year boundary
computes half of 2011 under the wrong design.

**Soften the overlap gate.** Rejected: the gate's uniqueness finding was true while
both editions declared the same token.

**Chosen: the design's own period codes, partitioned with `period_overrides`.**

## Constraints

- Revision selection stays on `(modelo, filing_year, period)` for every modelo.
- Period codes come from the record design; no synthetic token is introduced.

## Implementation

None beyond the registry period selectors that D4 of
`2026-06-01-registry-period-code-union-cli-boundary-adr` governs.

## Rationale

The governing fact is which design applies, and the designs differ in the period codes
they admit and in where 2011 falls. Declaring those codes resolves the year on the
existing triple, with no new persisted field and no date supplied by the operator.

## Consequences

- `test_every_modelo_resolves_exactly_one_revision_for_every_filing_year_through_today`
  asserts uniqueness for modelo 308 on the same terms as every other modelo.
