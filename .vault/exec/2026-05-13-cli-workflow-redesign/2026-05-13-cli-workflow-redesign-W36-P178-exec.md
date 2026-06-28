---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W36.P178'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W36.P178`

Completed the de-shim and de-stub cleanup phase for the legal IVA
prorrata substrate.

- Modified: `src/aeat/domain/vat/test_prorrata.py` (boundary tests
  landed in the same edit as P177; the CLI-surface test belongs to
  P178's scope)
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

The audit found no prorrata-related shim, stub, or placeholder anywhere
in `src/aeat/`. The ADR's rejected shapes (`app ledger prorrata`,
`app prorrata`, `aeat prorrata`, `usage_ratios -> prorrata`
translation) have no representation in code, no help text reference,
and no test asserting their behaviour. There was nothing to delete; the
phase deliverable is the regression guard that prevents re-introduction.

`test_no_parallel_prorrata_cli_surface_exists` walks `entrypoints/cli/`
and asserts that no Typer command decoration names `prorrata` or
registers a `prorrata` sub-app. The accepted operator path declared by
the ADR is consumption via `aeat app modelo bindings list --modelo
303 | 390`, where the binding readiness output surfaces a "prorrata
percentage missing" category. That surface lives in W47
(app-modelo-bindings-shape); this phase confirms no parallel verb
sneaks in ahead of the bindings surface.

Closed plan rows: `W36.P178.S1063`, `W36.P178.S1064`,
`W36.P178.S1065`, `W36.P178.S1066`, `W36.P178.S1067`,
`W36.P178.S1068`.

## Tests

`uv run --no-sync pytest src/aeat/domain/vat/test_prorrata.py -q`

The CLI-surface boundary test passes; full prorrata test slice runs
at 35 cases including all three boundary regression guards.
