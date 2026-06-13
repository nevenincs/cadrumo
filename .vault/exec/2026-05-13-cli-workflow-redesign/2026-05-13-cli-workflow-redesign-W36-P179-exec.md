---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W36.P179'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W36.P179`

Completed the real-behaviour verification phase for the legal IVA
prorrata substrate.

- Created: `src/aeat/application/aggregation/_prorrata.py`
- Created: `src/aeat/application/aggregation/test_prorrata.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

Added `aeat.application.aggregation._prorrata` as the bridge between the
bucket's persisted IVA operations and the pure prorrata domain
calculator. The aggregator is the application-layer service the ADR
mandates: it accepts a sequence of already-classified `VatOperation`
records and produces a `ProrrataInputs` value ready for
`compute_prorrata_general` consumption.

The module exposes three public callables:

- `aggregate_prorrata_inputs(operations, *, year) -> ProrrataAggregation`
  filters operations to the target year and routes each base amount
  into the deduction-eligible pool, the exempt pool, or the LIVA art.
  104 exclusion bucket. The result carries per-pool counts and the
  excluded amount total for downstream provenance.

- `aggregate_provisional_prorrata(prior_year_operations, *,
  prior_year, current_year, period)` is the LIVA art. 105
  orchestrator. It aggregates the prior year's actuals and stamps the
  resulting percentage with the current year and the in-year period
  token (`Q1`-`Q4` or `M01`-`M12`).

- `aggregate_definitiva_prorrata(current_year_operations, *, year)` is
  the LIVA art. 109 orchestrator. It aggregates the year's actuals and
  produces a `DEFINITIVA` `ProrrataResult` ready for the year-end
  regularisation entry on Q4 303 (casilla 44) and Modelo 390 (casilla
  33).

`VatOperationKind` distinguishes the three routing destinations:
`GRANTS_DEDUCTION`, `EXEMPT_WITHOUT_DEDUCTION`, and
`EXCLUDED_BY_ART_104`. The classification source tag (free-form short
string such as `vat-classify:R10-ic-supply` or `liva-art-20.1.23-rental`)
travels with each operation so the calculation revision's source trace
stays legible.

16 real-behaviour integration tests in
`src/aeat/application/aggregation/test_prorrata.py` cover pool-routing
contracts, year-filter behaviour, art. 104 exclusion handling,
provisional/definitiva orchestration semantics, and schema validation
(negative amounts rejected, extras forbidden, frozen models, empty
operation-id rejected). No tautological assertions; the prorrata
percentage itself is computed by the domain calculator, whose tests
already establish its correctness.

Closed plan rows: `W36.P179.S1069`, `W36.P179.S1070`,
`W36.P179.S1071`, `W36.P179.S1072`, `W36.P179.S1073`,
`W36.P179.S1074`.

## Tests

`uv run --no-sync pytest src/aeat/application/aggregation/test_prorrata.py src/aeat/domain/vat/test_prorrata.py -q`

51 prorrata tests pass (32 domain calculator + 16 application
aggregator + 3 boundary regression guards). The full `domain/vat`
suite still passes at 172 cases.
