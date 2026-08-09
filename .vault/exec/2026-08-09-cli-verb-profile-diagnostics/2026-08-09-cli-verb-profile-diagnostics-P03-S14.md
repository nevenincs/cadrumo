---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:337571773880b345051b80112b7493d9e9d273c45b7e5658df73ed7bcc4cd436'
step_id: 'S14'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add the enriched requires and diagnostics locale strings with real translations in all four catalogues

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Added `cli.diagnostics.summary.profile_missing_fields` through the locale CLI in all four catalogues with real translations, carrying both a `%{count}` and a `%{fields}` placeholder.
- Removed the superseded count-only `cli.diagnostics.summary.profile_missing_keys` from all four catalogues after confirming no remaining code reference.
- Left the `app modelo requires` warning key unchanged: its existing text already reads correctly for the enriched content, since it names "coefficient(s)" the profile has not set and the enriched list names exactly those.

## Outcome

Both new operator-facing strings exist in all four catalogues with real translations, and both superseded keys are gone.

Not adding a new key for the requires warning is the deliberate part. Its wording was already true of the enriched content, and replacing it would have forced a re-translation in four catalogues for no change in meaning, while breaking any operator's familiarity with the message.

## Verification

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

Before the superseded keys were removed the same check reported them as `extra` in all four catalogues, which is what identified them as unreferenced.

## Notes

No placeholder or self-referencing value was used in any catalogue; each locale carries a real translation.
