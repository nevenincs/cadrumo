---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a63e660a63c669be8fa5fd609ba598d2659339439c0bccae3b1b9303c7f24b21'
step_id: 'S13'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Harden the row-scoped locator to an exact expediente_id match instead of a substring filter, reusing the existing re import rather than a second selection idiom, with a test proving it cannot match a second row whose id merely contains the target as a substring

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py (_row_locator_for_expediente)`

## Description

## Outcome

## Verification

## Notes
