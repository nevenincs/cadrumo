---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m202-label-drift-repair-exec]]'
  - '[[2026-05-27-schema-hardening-m100-validation-repair-exec]]'
---



# `schema-hardening` `m100-marriage-citation-repair`

Repaired the M100 2024 marriage-month source-citation blocker exposed by
the backend registry validation gate.

## Description

Active M100 2024 and 2025 WIP added marriage-month formulas and profile bindings.
Those entries cited `aeat-renta-2024-manual-parte1` with required text for
`primer mes` and `último mes`, with the parallel 2025 entries citing
`aeat-renta-2025-manual-parte1` for the same phrases. The cited corpus did
not contain those phrases. The entries already declared the annual BOE form
sources, so the source-citation rows now cite those BOE form sources with
the same stable annual Modelo 100 evidence text used elsewhere in each
revision.

## Tests

Initial rerun after the 2024 repair exposed the same 2025 citation mismatch.
Passed after both annual repairs:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Result: 13 passed in 56.41 seconds.
