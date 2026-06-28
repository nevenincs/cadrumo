---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-18'
modified: '2026-05-18'
related:
  - "[[2026-05-18-schema-hardening-plan]]"
  - "[[2026-05-18-schema-hardening-research]]"
---

# `schema-hardening` audit: period-code coverage across the modelo corpus

## Scope

Read-only sweep of all 26 modelo TOML files for casillas, header
fields, and binding selectors that carry a filing-period value.
Goal: enumerate the corpus footprint of the `period_code` semantic
type so Plan A P03 retrofits land deterministically and Plan C
filing_period role rollout has a complete coverage list.

## Casilla-level period surfaces

| modelo | casilla id | data_type before | data_type after | period family |
|--------|-------------|------------------|------------------|----------------|
| 303    | decl.periodo | text | period_code | quarterly + monthly |
| 322    | decl.periodo | text | period_code | monthly |
| 349    | rect.periodo-rectificado | text | period_code | quarterly + monthly |
| 353    | decl.periodo | text | period_code | quarterly |
| 369    | decl.periodo (3 revisions) | text | period_code | EXT-quarterly |

Total casilla retrofits applied in P03: 7 casilla instances across 5
modelos. The fiscal-period inventory called out modelo 202 as
declaring IS-instalment periods (`1P`-`4P`), but the period value
is exposed only via export header_key on M202, not as a casilla.

## Header-key and binding period surfaces (deferred)

The remaining 21 modelos expose period via export `header_key` or
revision-level `period_selector` blocks rather than casilla
declarations. These surfaces fall outside `CasillaDefinition` and
are covered by:

- `period_selector` blocks: validated at revision load via the
  existing `PeriodSelector` model, which already enforces unique
  period values within a revision. The new `PeriodCode` alias
  could be threaded through `PeriodSelector.periods` for stricter
  validation; deferred to a follow-up phase.
- Export `header_key` data_type: the `ExportField.data_type` Literal
  in `_schema.py` is a separate Literal with its own variant set
  (`text`, `integer`, `decimal`, `money`, `date`, `boolean`). A
  future ExportField extension would add a `period_code` variant
  here. Out of scope for Plan A P03.
- `BindingSelectorMap` values: validated by per-source typed
  selector models in `_bindings.py`. Where a binding selector
  carries a period value, the per-source model would carry the
  `PeriodCode` constraint. Out of scope for Plan A P03.

## Period-form coverage in the regex

`_PERIOD_CODE_RE` accepts six concrete forms documented in the
fiscal-period inventory:

| form | example | modelo footprint |
|------|---------|------------------|
| quarterly | `1T`, `2T`, `3T`, `4T` | 111, 115, 123, 130, 131, 202, 303, 353, 390 |
| IS instalment | `1P`, `2P`, `3P`, `4P` | 202 (header only) |
| annual | `0A` | 184, 232, 720, 840 |
| monthly | `01` through `12` | 303, 322, 349, 369 |
| OSS quarter | `EXT-1T` through `EXT-4T` | 369 (the only OSS modelo) |
| ad-hoc | `AD-HOC`, `EVENT-N` | 308, 309 (event-driven) |

No casilla declaration in the corpus uses a period form outside
this set. Future modellers introducing a new form must extend
`_PERIOD_CODE_RE` and add a corresponding roundtrip test fixture.

## Cross-modelo drift open issue

The fiscal-period inventory flagged a real cross-modelo drift:

- Modelo 202 uses `1P`-`4P` for IS instalments; modelo 369 uses
  `EXT-1T`-`EXT-4T` for OSS extra-Union quarters; other quarterly
  modelos use plain `1T`-`4T`. The `PeriodCode` alias accepts all
  three because each represents a legally distinct period family
  carrying different legal_refs.

Plan C's `filing_period` semantic role (planned in `W04.P12`)
addresses the cross-modelo identity layer by binding the
filing_period role to its modelo's period family. Until Plan C
lands, `data_type = "period_code"` is permissive across families.

## Validator hard-flip status

Plan A P03.S46 (turn on hard-error snapshot validation rejecting
`text` declarations on casillas whose id matches `decl.periodo` or
`rect.periodo-rectificado`) is superseded by Plan C's semantic_role
consistency validator (Plan C `W01.P01.S04`), which enforces the
same property through role binding rather than id-pattern matching.
The Plan A step is deferred without standalone implementation.
