---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:2862625c8211cd4cbca8245e96c14030a6c19b650514a536b09560c3f20447c6'
step_id: 'S47'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the LibreOffice executable field as an external-executable escape carrying its role, gated by the binding gate seeing it once the selector widens

## Scope

- `src/cadrumo/core/config.py`

## Description

- Declare `cadrumo_libreoffice_executable` in `EXTERNAL_PATH_SETTINGS_FIELDS` with `ExternalPathRole.EXTERNAL_EXECUTABLE` and a stated reason.
- Widen the field selector from name-suffix matching to `Path`-typed annotation discovery so an inconveniently-named field cannot hide.

## Outcome

Landed in commit `3ee34dc721`, alongside S48 (selector widening, already checked).

## Notes
