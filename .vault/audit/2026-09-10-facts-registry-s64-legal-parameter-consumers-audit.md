---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:04820112b09a01fd206e5ee9816d90aab1716d465699f7bdd1b8416185aaf069'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# `facts-registry` audit: `S64 legal-parameter consumer migration`

## Scope

Reviewed the S64 legal-parameter consumer migration against the accepted facts
catalogue decision, its four research records, the consumer-migration reference,
and the current worktree diff. The review covered the objective-estimation
advisory, retención parameter projections, Modelo 036 activity-selector
partitions, the legal-parameter fact provider, their focused tests, the S64 plan
row, and this audit scaffold.

## Findings

### fabricated-temporal-validity | high | The provider asserts current legal parameters were valid for every filing date

`_parameter_fact` publishes every adapted `LegalParameter` with
`valid_from=date.min` and no end date. The bundled administrator-rate evidence
states that the 19-percent reduced rate and EUR 100,000 threshold did not exist
before 2015-01-01; nevertheless an authority query for the reduced-rate fact at
2010-12-31 resolves 0.19. This is a filing-affecting false historical result,
not an absence or an advisory, and therefore violates the required exact,
temporally applicable, fail-closed authority semantics. The focused provider
tests prove only 2025 resolution and do not exercise this known boundary.

### administrator-unit-mismatch | high | The migrated administrator-rate loader rejects the bundled legal fact

`load_administrador_retencion_rates` requests the threshold fact with expected
unit `eur`, but its authoritative parameter declares `EUR`. The provider
preserves that unit exactly, so the loader raises `TransactionValidationError`
instead of returning the statutory rate record. The focused administrator test
suite reproduces the failure through the public loader; this is a regression in
an operative legal-fact consumer, not a malformed-corpus refusal.

### runtime-date-selection | medium | Period-aware consumers discard their filing period and select law by execution day

The migrated `tipo_actividad_code_set` defaults to `date.today()` when its
caller omits a coordinate. Both the Modelo 131 agrarian aggregation and the
Art. 109 coverage calculation already receive a `Period` but call it without
the period end. The retención public projections and legal-reference helpers do
the same. Once a selector or rate gains a dated variant, recalculating the same
filing period on different days can select different law, defeating
reproducibility and the authority result's stated temporal coordinate.

## Recommendations

- Resolve `fabricated-temporal-validity` before accepting S64: preserve each
  supported parameter's evidenced legal window in the fact projection, or
  refuse dates the legacy shape cannot ground. Add real-authority tests for the
  pre-2015 administrator boundary and for no-match refusal outside each
  supported window.
- Resolve `administrator-unit-mismatch` before accepting S64: use the canonical
  registry unit token for the threshold or canonicalise it at the owning typed
  unit boundary, then retain a focused public-loader test that exercises the
  actual bundled `EUR` declaration.
- Resolve `runtime-date-selection` with the first finding: require callers with
  a filing period to pass its explicit legal coordinate, and make convenience
  APIs either require that coordinate or explicitly remain non-filing-grade.
  Add regression tests that a historical period keeps its selected variant when
  evaluated after a later variant begins.
