---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W33.P163'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W33.P163`

De-shim / de-stub phase. Confirmed there is no operator-facing
`oss` / `ioss` CLI root and no `app vat oss` carve-out.

- Created (within the test for P161): boundary test
  `test_no_cli_root_oss_or_ioss_verb_is_registered` in
  `src/aeat/application/aggregation/test_oss_ioss.py`.

## Description

Per the ADR, OSS / IOSS is a Modelo 369 calculation concern, not an
operator domain. The CLI root accepts only `aeat config` and
`aeat app`; OSS / IOSS is consumed through `aeat app modelo
calculate --modelo 369` only.

The boundary test walks
`src/aeat/entrypoints/cli/` and asserts no `.py` source file
registers a Typer / Click verb whose name is `oss`, `ioss`, or any
of the rejected `app vat oss` / `app vat ioss` carve-outs the ADR
calls out. The scan looks for the literal forms a verb registration
would take (double- or single-quoted command-name strings, or
`name="oss"` / `name="ioss"` kwarg patterns).

No pre-existing stub exists (the wrapper is new in this wave), so
the de-stub limb is vacuously satisfied. The boundary test is the
forward guard.

Closed plan rows: `W33.P163.S0973`, `W33.P163.S0974`,
`W33.P163.S0975`, `W33.P163.S0976`, `W33.P163.S0977`,
`W33.P163.S0978`.

## Tests

`uv run --no-sync pytest
src/aeat/application/aggregation/test_oss_ioss.py
-k no_cli_root_oss_or_ioss_verb -q` — 1 / 1 pass.
