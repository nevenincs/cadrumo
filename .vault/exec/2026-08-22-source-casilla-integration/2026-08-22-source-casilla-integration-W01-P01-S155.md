---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:cb4e11edd25efda4ea69438a00ae27ef84c514173db312800e2e68e385caa1d8'
step_id: 'S155'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# correct composite-provenance documentation and validation language identified by formal review

## Scope

- `src/cadrumo/domain/modelos`

## Description

- Replace retired provenance field names in the persisted carrier documentation.
- Make contributor-axis validation errors name the exact strict schema fields.
- Update the contract assertion for the corrected diagnostic language.

## Outcome

The persisted provenance contract and its failures now describe the same canonical resolved/contributor schema exposed by the model.

## Notes

Corrective work originated from the MEDIUM finding in the formal S135 quality review. The focused domain contract test and Ruff check passed.
