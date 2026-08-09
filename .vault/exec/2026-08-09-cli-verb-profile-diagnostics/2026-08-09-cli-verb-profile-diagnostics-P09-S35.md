---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:5dcbe318524a37182b9fde7fe5c1be29bb0945f68f02c831c6517acfdb47b283'
step_id: 'S35'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Update the two live-auth refusal locale strings to carry a requirements placeholder with real translations in all four catalogues

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Rewrote both strings through the locale CLI in all four catalogues, replacing the dotted path with a `%{requirements}` placeholder and keeping each sentence's remaining guidance intact.

## Outcome

Neither string now carries a profile field name; the schema supplies it.

Both were rewritten in place rather than replaced with new keys, since the meaning is unchanged and introducing new keys would have retired two live keys for no semantic difference.

## Verification

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

## Notes

Every mutation went through the locale CLI; no catalogue file was hand-edited and no placeholder or self-referencing value was used.
