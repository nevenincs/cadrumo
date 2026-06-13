---
step_id: S79
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S79 — no_active_profile locale enrollment

## Outcome

Replaced the bare-string dict / text emit in `_active_profile_or_exit` at
`src/aeat/entrypoints/cli/_common.py:139-140` with `tr()` calls:

- `tr("cli.common.errors.no_active_profile_error_value")` for the `"error"`
  dict value and the text-channel tab-separated line.
- `tr("cli.common.next.create_profile_command")` for the `"next"` dict value
  and the text-channel line.

Both keys were scaffolded via `python -m aeat.locales scaffold` and set for
all four locales:

- `cli.common.errors.no_active_profile_error_value`:
  en `no-active-profile`, es `sin-perfil-activo`, ca `sense-perfil-actiu`,
  hu `nincs-aktiv-profil`
- `cli.common.next.create_profile_command`:
  en `aeat config profile create NAME`,
  es `aeat config profile create NOMBRE`,
  ca `aeat config profile create NOM`,
  hu `aeat config profile create NEV`

## Files touched

- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

`python -m aeat.locales audit` clean. `vault plan step check S79` applied.
