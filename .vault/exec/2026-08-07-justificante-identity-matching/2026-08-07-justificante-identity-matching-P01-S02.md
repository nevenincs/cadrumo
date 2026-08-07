---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:00631d8ee8466be9f9d86887cc72808d7d80f55b830f4bdf3a7e7ac18d33cb0a'
step_id: 'S02'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Drop the now-signature-invalid expediente_id argument now that register_capture_justificante_metadata's existing csv equality check already covers identity

## Scope

- `src/cadrumo/application/live/_justificante.py (_justificante_matches_capture_axis)`

## Description

## Outcome

## Verification

## Notes
