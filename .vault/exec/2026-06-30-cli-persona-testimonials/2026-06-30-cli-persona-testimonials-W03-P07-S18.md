---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S18'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Harden Modelo 100 borrador observation binding and parser coverage

## Scope

- `src/aeat/adapters/inbound/borrador`

## Description

- Replayed the Modelo 100 borrador and predeclaracion evidence boundary against
  current parser behavior.
- Checked that draft and preview artefacts do not carry filed-evidence CSV
  authority.
- Grounded intent against AEAT Renta WEB and filed-declaration consultation
  surfaces.

## Outcome

Commit `1758194e5` fixed a current parser defect where a `VISTA PREVIA`
predeclaracion PDF with a CSV-looking footer exposed `csv` on the parsed
observation. Only `DECLARACION` artefacts now retain CSV values; `BORRADOR` and
`PREDECLARACION` force `csv=None`.

## Notes

Focused parser verification passed 18 tests. A broader borrador/modelo binding
gate remains blocked by unrelated dirty Modelo 100 registry semantic-role WIP.
