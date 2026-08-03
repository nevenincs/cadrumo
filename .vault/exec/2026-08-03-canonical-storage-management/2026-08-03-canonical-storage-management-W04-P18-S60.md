---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:c0295b5ac43637327bc818693863160805cbd26626d7160cf84237e5abbb4154'
step_id: 'S60'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the typed result payloads for the five verbs on the envelope spine with no bespoke advisory or next or suggestion field, gated by the registered-schema and no-bespoke-notice-field conformance tests

## Scope

- `src/cadrumo/entrypoints/cli/_config/_storage_payloads.py`

## Description

- Declare the five verbs' result payloads as registered `OutputSchema` subclasses on the envelope spine in `_storage_payloads.py`, with no bespoke advisory/next/suggestion field.

## Outcome

Landed in commit `ecd388183f`, with a follow-up fix in `49f6ec4ec0` for the config-help builder's line-count ceiling and a missing core-struct docstring cross-link the new payload module triggered.

## Notes
