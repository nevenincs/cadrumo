---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:59e7738d285da142fc211ba1d749d134eee1cc9b9e16415e60be5c558bdd6c1e'
step_id: 'S207'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Privatize the ledger_binding_resolution implementation after eliminating every external consumer and public package reach

## Scope

- `src/cadrumo/domain/calculations/registry/ledger_binding_resolution.py`

## Changes

R src/cadrumo/domain/calculations/registry/ledger_binding_resolution.py -> _ledger_binding_resolution.py
A src/cadrumo/domain/calculations/registry/quantity_screen_enrolment.py
M src/cadrumo/domain/calculations/registry/ledger_bindings.py
M src/cadrumo/domain/calculations/registry/invoice_bindings.py
M src/cadrumo/domain/calculations/registry/irnr_ledger_bindings.py
M src/cadrumo/domain/calculations/registry/ledger_impatriado_bindings.py
M src/cadrumo/domain/calculations/registry/tests/test_invoice_measure_classification.py
M src/cadrumo/domain/calculations/registry/tests/test_ledger_quantity_screen_partition.py
M src/cadrumo/application/aggregation/tests/test_quantity_screen_enrolment.py
M src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py
M dev/quality/registry_facade_family_census.v1.json

## Notes

The row asks to privatize after eliminating every external consumer. One
external consumer could not be eliminated: `screened_quantity_families` backs a
completeness gate in `application/aggregation/tests/test_quantity_screen_enrolment.py`
which asserts that the enrolment inventory equals the registry's screened set.
Its own docstring records that this comparison is what makes the per-family
drives a gate rather than a sample, so deleting the reach would have downgraded
a gate to a sample.

The enrolment registry is therefore a genuine cross-package contract while the
binding resolution beside it is registry-internal. Per the architecture rule for
a contract required outside its package, the contract hard-moved to its own
public defining module and the resolution internals were privatised. Every
consumer now names whichever of the two it actually needs.

The census row was re-adjudicated to record the new defining owner. Reviewed
fields must be edited and then passed through `--refresh-reviewed`; checking
before refreshing, or hand-writing the artifact, fails on derived-field drift.

`test_keep_public_family.py` dropped this row from its outstanding table, which
its own staleness assertion required once the terminal state was reached.
