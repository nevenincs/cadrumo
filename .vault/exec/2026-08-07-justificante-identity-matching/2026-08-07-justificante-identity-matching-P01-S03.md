---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ce9332883b14950b2a2a75239b2cbbcfa6d4218c05f499086b60964dc4caa537'
step_id: 'S03'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Drop the now-signature-invalid expediente_id argument now that register_capture_as_filing_evidence's existing csv equality check already covers identity

## Scope

- `src/cadrumo/application/live/_justificante.py (register_capture_as_filing_evidence)`

## Description

## Outcome

## Verification

## Notes
