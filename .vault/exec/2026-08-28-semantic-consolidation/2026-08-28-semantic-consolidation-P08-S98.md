---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:fe3e707f4a15ba22695e5f1f6b0789f8a3644c78e607a6309e3deb1510bc3ba1'
step_id: 'S98'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Repoint the setup-answers lazy module accessor at deadlines.models, and move the FiscalResidency reads to the renta-code module that actually defines them

## Scope

- `src/cadrumo/core/setup_answers.py`

## Changes

- `M` `src/cadrumo/core/setup_answers.py`
- `verify:` `pytest src/cadrumo/core/tests/test_setup_answers.py -n 0 -m ""` -> `pass`

## Notes

FiscalResidency was never a deadlines symbol: the namespace re-exported it from
`contribuyente.renta_codes`, and the accessor for that module was already
defined beside the one being repointed.
