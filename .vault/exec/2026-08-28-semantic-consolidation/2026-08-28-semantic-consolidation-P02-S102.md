---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:7687217ed716e17e3a26422a24b5c4b57071bea19896f97c2f96db0788ea9b65'
step_id: 'S102'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Adopt the canonical filing-year bounds in the work-lifecycle CLI, which redeclared FILING_YEAR_MIN and FILING_YEAR_MAX as local literals

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`

## Changes

- `A` `src/cadrumo/application/evidence/bundle_text.py`
- `M` `src/cadrumo/application/evidence/_models.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`
- `verify:` `pytest src/cadrumo/application/evidence -n 0 -m ""` -> `pass`

## Notes

The notes bound was written out identically at both sites. The completeness
ratio ran the other way: the CLI already used the canonical `UnitFraction`
while the manifest model restated `ge=0.0, le=1.0` by hand, so the projection
was more canonical than its own source.
