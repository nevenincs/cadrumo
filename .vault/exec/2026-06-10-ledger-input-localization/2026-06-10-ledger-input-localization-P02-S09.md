---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S09'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---




# Add %{label} and %{raw} interpolations to cli.common.errors.invalid_iso_date for en, ca, and hu locales using python -m aeat.locales set so all four locales carry the same interpolation tokens as the existing es string

## Scope

- `src/aeat/locales/`

## Description

- Added the `%{label}` and `%{raw}` interpolation tokens to `cli.common.errors.invalid_iso_date` for the en, ca, and hu locales (es already carried them) via the `aeat.locales` CLI.

## Outcome

Done. Verified at HEAD: all four locales carry `%{label}` and `%{raw}` in `invalid_iso_date`; key parity holds.

## Notes

None.
