---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m308-standardization-plan]]'
  - '[[2026-05-27-schema-hardening-m308-standardization-P01-S04]]'
---



# `schema-hardening` `m100-validation-repair`

Closed the M100 validation edge exposed while verifying the all-directory
registry substrate.

## Description

The broader loader and cross-revision drift gate initially failed on active
M100 2024 WIP. The new taxpayer birth-date binding had an incomplete
source-citation row, which made the registry unloadable. Completing the
citation with the same BOE form text used by adjacent 2024 bindings restored
loadability.

The M100 calculation WIP also added age-aware minimum-contributor logic.
Regression tests for the settlement and ahorro chains now provide explicit
date-binding values, matching the formula contract instead of relying on
implicit defaults.

## Tests

Passed:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py src/aeat/domain/calculations/registry/test_modelo_100_ahorro_base_chain.py src/aeat/domain/calculations/registry/test_modelo_100_settlement_chain.py -q`

Result: 48 passed in 150.29 seconds.
