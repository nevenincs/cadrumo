---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W33.P162'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W33.P162`

Shadow duplicate removal phase. Asserted the canonical aggregator is
the sole non-registry consumer of the
`ledger_oss_aggregation` binding resolver.

- Created (within the test for P161): boundary test
  `test_no_parallel_oss_ioss_aggregator_exists` in
  `src/aeat/application/aggregation/test_oss_ioss.py`.

## Description

The application-layer aggregator at
`src/aeat/application/aggregation/_oss_ioss.py` is the only module
permitted to consume
`aeat.domain.calculations.registry.resolve_ledger_oss_aggregation_binding_values`
in non-test source code. The registry's `_bindings.py` module is
exempt because that is where the resolver is defined; the registry
package `__init__.py` is exempt because it re-exports the resolver as
part of its public surface.

The boundary test walks `src/aeat/`, skips `test_*.py` files, skips
the canonical wrapper, skips `_bindings.py` under
`domain/calculations/registry/`, skips the registry `__init__.py`,
and asserts the forbidden identifier
(`resolve_ledger_oss_aggregation_binding_values`) does not appear in
any other source file.

The test currently passes because no parallel OSS / IOSS aggregator
was ever landed; it is the regression guard against a future agent
re-creating a local OSS aggregation helper inside
`entrypoints/cli/` or under another application package.

Closed plan rows: `W33.P162.S0967`, `W33.P162.S0968`,
`W33.P162.S0969`, `W33.P162.S0970`, `W33.P162.S0971`,
`W33.P162.S0972`.

## Tests

`uv run --no-sync pytest
src/aeat/application/aggregation/test_oss_ioss.py
-k no_parallel_oss_ioss_aggregator -q` — 1 / 1 pass.
