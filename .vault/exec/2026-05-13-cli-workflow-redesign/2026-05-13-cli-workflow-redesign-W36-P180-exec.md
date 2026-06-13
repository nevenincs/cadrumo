---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W36.P180'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W36.P180`

Completed the thin-CLI-exposure phase for the legal IVA prorrata
substrate.

- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

Per the ADR, prorrata has no direct operator-facing CLI verb. The
accepted consumption path is `aeat app modelo bindings list --modelo
303 --year YYYY --period Q1` (or `390`), where the modelo-bindings
surface (owned by W47, app-modelo-bindings-shape) reports a "prorrata
percentage missing" readiness category and points the operator at the
profile axis or the provisional/definitiva calculation that resolves
it. Direct `aeat prorrata`, `aeat app prorrata`, and `aeat app ledger
prorrata` are rejected by the ADR's Constraints.

The thin-CLI deliverables are therefore confirmation-only for this
phase:

- The boundary test `test_no_parallel_prorrata_cli_surface_exists`
  (landed in P178) is the regression guard that prevents a parallel
  prorrata CLI verb from being registered. It walks
  `entrypoints/cli/` and asserts no Typer command names `prorrata`.
- Argument parsing, backend delegation, `_emit` rendering, and the
  central command-error boundary all apply when the W47
  `app modelo bindings list` surface lands and exposes prorrata
  readiness. The prorrata substrate is wired through the application
  aggregator created in P179; no CLI handler in W36 owns prorrata
  directly.
- Help text correctness is enforced at W47's level by the
  modelo-bindings ADR; W36 contributes no help text of its own.

`VatOperationKind`, `ProrrataAggregation`, and the three orchestrators
live under `aeat.application.aggregation` (a public package surface)
so the W47 bindings provider can consume them without reaching into
private modules.

Closed plan rows: `W36.P180.S1075`, `W36.P180.S1076`,
`W36.P180.S1077`, `W36.P180.S1078`, `W36.P180.S1079`,
`W36.P180.S1080`.

## Tests

`uv run --no-sync pytest src/aeat/application/aggregation/test_prorrata.py src/aeat/domain/vat/test_prorrata.py -q`

51 prorrata tests pass. The CLI-surface non-existence is guarded by
`test_no_parallel_prorrata_cli_surface_exists`.

## Wave summary

W36 (IVA prorrata arts. 101-103) is complete end-to-end. The wave
delivered:

- A pure-domain substrate at `aeat.domain.vat._prorrata` with five
  StrEnum types, four immutable Pydantic models, five pure
  calculators, and three new error codes.
- An application aggregator at `aeat.application.aggregation._prorrata`
  with one operation model, one aggregation result model, one pure
  aggregator, and two lifecycle orchestrators (provisional /
  definitiva).
- Three boundary regression guards that prevent re-introduction of
  the ADR's rejected shapes.
- 51 real-behaviour tests; no tautological assertions; LIVA arts.
  101-105 and 109 plus art. 9.1.c and art. 104 cited in source.

Plan progress: 38/1770 Steps closed (2.1%). W01 (P001 only) and W36
(P176-P180) are both fully complete.
