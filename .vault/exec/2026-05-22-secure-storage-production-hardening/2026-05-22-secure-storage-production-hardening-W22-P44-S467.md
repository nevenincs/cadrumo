---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S467'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Audit and correct custody recovery guidance to name `config switch` only

## Scope

- `src/aeat/locales`

## Description

- Scanned all runtime locale catalogues for the retired `config unlock` spelling.
- Ran `uv run --no-sync python -m aeat.locales scaffold --check`.
- Ran `uv run --no-sync python -m aeat.locales audit`.

## Outcome

No locale catalogue contains retired unlock guidance. Scaffold drift and locale
health checks pass for Catalan, English, Spanish, and Hungarian, so no locale
mutation was needed.

## Notes

Locale files were not hand-edited. The locale CLI remains the authoring and
verification authority for this surface.
