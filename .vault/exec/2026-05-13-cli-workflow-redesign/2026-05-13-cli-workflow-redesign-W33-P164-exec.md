---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W33.P164'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W33.P164`

Real-behaviour verification. Seventeen tests grounded in three
external authorities: the BOE-published Spanish VAT rate registry,
Real Decreto-ley 7/2021 + Orden HAC/610/2021 (OSS / IOSS
transposition), and LIVA art. 163 unvicies / octiesdecies /
quinvicies.

- Created: `src/aeat/application/aggregation/test_oss_ioss.py`

## Description

Every test grounds its expected outcome in an externally-published
authority — never the test author's re-application of the
wrapper's own formula:

- DE general rate = 19 % per `registry/aeat/vat/rates.toml`. Tests
  feeding a candidate with `base = 100, iva = 19` for destination
  DE assert PASS because the German rate (anchored to the UStG
  and Council Directive 2006/112/EC) is 19 %, not because the
  wrapper calls the formula and agrees with itself.
- FR general rate = 20 % per the same registry. Tests confirm the
  wrapper accepts any of the 27 registered Member States, not just
  Germany.
- IT general rate = 22 % per the same registry. The empty-match
  test seeds a candidate at IT 22 % to verify the binding resolver
  emits a zero aggregate when no candidate matches the DE-services
  selector.

Suite breakdown:

- Candidate schema (2 tests): strict / frozen / extras-forbid;
  negative amounts rejected.
- IVA rate validation (7 tests): DE accept, FR accept, six-EUR-off
  reject on DE, zero-IVA reject when destination rate is non-zero,
  one-cent rounding accepted, two-cent drift rejected, structured
  diagnostic context attached to the error, pre-registry date
  raises `VatRateNotFoundError`.
- Batch helper (2 tests): order preserved, fast-fail on the first
  bad row.
- Full pipeline (3 tests): routes validated observations into the
  Modelo 369 Esquema Unión revision, never reaches the resolver
  when any candidate is invalid, returns zero for an empty-match
  binding.
- Boundary regression guards (2 tests): no parallel aggregator
  outside the canonical module, no CLI root OSS / IOSS verb.

Result: 17 / 17 OSS / IOSS pass. Wider aggregation +
Modelo 369 registry + OSS substrate suites remain green at
131 / 131.

Closed plan rows: `W33.P164.S0979`, `W33.P164.S0980`,
`W33.P164.S0981`, `W33.P164.S0982`, `W33.P164.S0983`,
`W33.P164.S0984`.

## Tests

`uv run --no-sync pytest src/aeat/application/aggregation/ src/aeat/domain/calculations/registry/test_ledger_oss_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_369_registry.py src/aeat/domain/vat/test_oss.py -q`
— 131 / 131 pass.
