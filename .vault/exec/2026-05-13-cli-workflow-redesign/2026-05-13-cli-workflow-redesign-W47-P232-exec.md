---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W47.P232'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W47.P232`

Shadow-duplicate removal phase. The boundary test
`test_no_parallel_bindings_typer_outside_canonical_module` asserts
the `bindings` sub-Typer is registered only in `_modelo.py`.

## Description

The legacy `@app.command("bindings")` single-command form is
deleted in P231; this phase pins the new sub-Typer as the only
declaration of a Typer named `bindings` anywhere under
`src/aeat/entrypoints/cli/`.

The boundary test walks the CLI tree, skips test files (which
legitimately quote the forbidden patterns as search strings in
their own boundary scans), and asserts no other source file
contains `typer.Typer(name="bindings")` or the multi-line
variant. The test currently passes because the canonical module
is the only declaration.

Closed plan rows: `W47.P232.S1387`, `W47.P232.S1388`,
`W47.P232.S1389`, `W47.P232.S1390`, `W47.P232.S1391`,
`W47.P232.S1392`.

## Tests

Boundary test passes as part of the
`src/aeat/entrypoints/cli/test_modelo.py` suite.
