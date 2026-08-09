---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:608e38c361126f129cea2bf0d83ee6974abe6d39241bd7b92eff1a6a92c5bd94'
step_id: 'S39'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Update the two Cl@ve credential locale strings to carry field placeholders with real translations in all four catalogues

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Rewrote both strings through the locale CLI in all four catalogues, replacing each embedded storage path with a placeholder and preserving the remaining guidance, including the contraste string's NIE-versus-DNI branch.

## Outcome

No profile field name remains in either string.

The contraste string keeps two distinct placeholders so its conditional guidance survives translation. A translator can reorder the clauses freely without breaking which field belongs to which document type, which a single combined list would not have allowed.

## Verification

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

## Notes

Every mutation went through the locale CLI; no catalogue file was hand-edited and no placeholder or self-referencing value was used.
