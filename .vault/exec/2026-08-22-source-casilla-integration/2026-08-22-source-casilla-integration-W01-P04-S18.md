---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:29dc547bb0f56ed31cd20b02541abc2e68289eb08b9ffd89a1f563959264c437'
step_id: 'S18'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# load and validate the census against the closed contract

## Scope

- `src/cadrumo/application/registry/source_connectivity.py`

## Description

- Load the bundled TOML census through a strict frozen versioned manifest model.
- Reuse the canonical core census-row and closed disposition contracts.
- Hydrate TOML arrays into immutable tuples and require live authority for connected proofs.
- Refuse duplicate candidate identities and unknown manifest fields.

## Outcome

The canonical census is now loadable only through the existing governed row contract. Blocked, candidate, manual, and connected states inherit their established evidence, ownership, follow-up, expiry, and live-proof validation requirements.

## Notes

Ruff and bundled-load checks passed. A direct strict-schema probe proved unknown manifest fields are refused. No parallel disposition or connected-proof vocabulary was introduced.
