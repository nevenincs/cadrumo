---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:8d0d96aa67f5b4dc8c28eb4079a80288f1f424a13bb1ee13ce32ed865937049d'
step_id: 'S38'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Name both Cl@ve contraste fields by their schema-derived labels in the missing-contraste credential refusal

## Scope

- `src/cadrumo/application/auth/_sessions.py`

## Description

- Passed both contraste field labels on the refusal's context under separate keys, and removed both storage paths from the sentence.

## Outcome

The refusal names both fields by label while keeping its conditional structure intact.

Two placeholders were used rather than one combined list because the sentence is genuinely conditional: one field applies to a NIE holder and the other to a DNI holder, and collapsing them into a single list would have told every operator to record both. Preserving the branch keeps the instruction correct for each document type.

The refusal CONDITION is unchanged, including the guard that only applies it to the non-QR route. The QR route asks for neither field and is still not refused for their absence.

## Verification

    uv run --no-sync pytest src/cadrumo/application/auth -m "unit or integration" -n 0 -q
    319 passed in 75.35s (0:01:15)

## Notes

Both fields resolve their labels from their paths, having no declared selectors.
