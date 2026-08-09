---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:f432a3653a043d665aecd3406633be919a352b0466db244d7ab72198bccb6f85'
step_id: 'S08'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add the enriched overview refusal locale strings with real translations in all four catalogues

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Added `cli.overview.refused_incomplete_profile` through the locale CLI in all four catalogues with real translations, carrying a `%{requirements}` placeholder for the enriched requirement list.
- Removed the superseded `cli.overview.calendar_refused_incomplete` from all four catalogues after confirming no code references it.

## Outcome

The refusal string is authored once per catalogue and reads correctly for the enriched content it now carries.

A new key was added rather than the old one reworded, because the old key's text was wrong for the new content in two ways beyond phrasing: it named the calendar specifically while three verbs share it, and its placeholder was called `keys`, which described the raw tokens the refusal no longer emits. Leaving a placeholder named `keys` holding operator labels and legal citations would have misled the next translator.

The old key was removed rather than left in place. This project carries no legacy compatibility surface, and an unreferenced key is drift the parity gate is entitled to flag.

## Verification

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

Before removing the superseded key the same check reported `extra cli.overview.calendar_refused_incomplete` in all four catalogues, which is what identified it as unreferenced.

## Notes

Confirmed no remaining Python reference to the removed key before removing it.
