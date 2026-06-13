---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m100-revision-drift-research]]'
---



# `schema-hardening` `m200-estado-share-binding-repair`

Cross-committed the Modelo 200 Estado-share profile binding validation repair.

## Description

The cross-revision drift test file's committed-corpus validation surfaced a
real registry blocker in an active Modelo 200 binding addition. The new
`modelo-200-2024-profile-tributacion-estado-porcentaje` binding referenced
an unregistered `ley-organica-8-1980-lofca:art-3` legal id and used a source
citation phrase that was not present in the committed 2024 Modelo 200 manual
PDF text.

The repair aligns the binding with the existing legal grounding already used
by the Modelo 200 casilla and formula for the same Estado-share calculation:
`ley-27-2014:art-41`, `ley-27-2014:art-29`, and `ley-27-2014:art-30`.
The source citation now uses the exact manual text
`Casilla [00625] Administración del Estado`.

## Tests

Initial failed gate, not swallowed:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Result: two committed-corpus validation failures on the M200 binding.

Follow-up validation is recorded in the M100 revision-drift test commit.
