---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:7400807e994f52640c35bdc1536bc0ea9d820bb8d1dd5a2bfd3fbb6bac60f3b0'
step_id: 'S58'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Validate and live-rehash filing-envelope and auxiliary-envelope-header source identities and digests against the catalogue, with missing, mismatched, and stale-digest mutation proof

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/application/registry/`

## Description

- Bind every embedded filing-envelope and auxiliary-header declaration to its canonical catalogue key, source identity, record-design kind, and declared digest.
- Re-hash the exact resolved catalogue source during registry validation whenever the supplied corpus root permits it.
- Thread the supplied source root only through the revision export-validation boundary.
- Exercise one shipped filing envelope and one shipped auxiliary header through snapshot construction, with missing, rebound, mismatched, and all-zero stale-digest mutations.

## Outcome

- Registry composition now refuses an embedded envelope or auxiliary header when its source declaration is missing, rebound, the wrong kind, digest-divergent, or stale against live bytes.
- Focused serial verification passed: `uv run --no-sync pytest -n 0 -x src/cadrumo/domain/calculations/registry/tests/test_embedded_envelope_source_authority.py` â€” 10 passed in 21.47s.
- Focused Ruff verification passed for the three validator modules and the new test module.

## Notes

- A broader historical coverage run was stopped after its known slow record-design path exceeded the agreed timebox; it was not used as completion evidence.
