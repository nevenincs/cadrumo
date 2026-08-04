---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:e0214524bc10634c600d17c1202f64a5033e002512c4f2e0aa54933e62e7b381'
step_id: 'S48'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Widen the path-typed field selector from name suffix to annotation so no path-valued setting can hide behind an inconvenient name, gated by a test asserting the selector now returns the LibreOffice field

## Scope

- `src/cadrumo/core/config.py`

## Description

- Widen the path-typed field selector from name suffix to annotation so no path-valued setting can hide behind an inconvenient name.

## Outcome

Landed in commit `3ee34dc721` ("give every path setting a declared home, or name it"). Verified at committed HEAD: `path_typed_settings_fields` (relocated to `core/tests/_settings_path_fields.py` by the later W03.P11 lifecycle-gate rewrite) selects via `annotation_mentions_path`, checking whether the field's type annotation admits `Path` (including `Path | None`), not the field name.

## Notes
