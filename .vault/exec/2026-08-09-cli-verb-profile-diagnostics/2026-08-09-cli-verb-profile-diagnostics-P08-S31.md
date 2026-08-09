---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:6758135ad721dcfe0b044c8d169622a0aa4f7e76d9d369ff378c7218c419f6ea'
step_id: 'S31'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Update the two refusal locale strings to carry a requirements placeholder with real translations in all four catalogues

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Rewrote both strings through the locale CLI in all four catalogues so the field names come from a `%{requirements}` placeholder rather than from the sentence.
- Removed the selector token from the wizard string and the two hard-coded paths from the export string.

## Outcome

Neither catalogue now carries a profile field name. The catalogues hold the sentence; the schema holds the names.

That separation is the durable part. While a field name lived in the catalogues, a schema rename had four places to be chased and no gate that would fail if one were missed, so the translations could silently drift out of step with the schema they described. A placeholder cannot drift.

Both strings were rewritten in place rather than replaced with new keys, because their meaning is unchanged: the same refusal, naming the same fields, sourcing the names differently. Introducing new keys would have retired two live keys for no semantic change.

## Verification

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

## Notes

Every mutation went through the locale CLI; no catalogue file was hand-edited, no placeholder or self-referencing value was used, and the intentional-identical allowlist was not touched.
