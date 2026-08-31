---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6828322820dcb59187c5cd0646ca0aa7f8b80cf2328b417fc08bea43b2325812'
step_id: 'S36'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Rule on filing-record import versus observe-local: not a conflation, they sit on opposite sides of the official-AEAT-evidence boundary and both stay

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `.vault/audit/2026-08-25-cli-root-verb-homes-audit.md`
- `M` `.vault/audit/2026-08-26-cli-root-verb-homes-close-honesty-audit.md`
- `verify:` `is_official_aeat accepts every filing-record import evidence kind and no observe-local kind` -> `pass`

## Notes

No code change. The Step is a ruling: the two verbs are not a conflation. Their
evidence kinds fall on opposite sides of `is_official_aeat`
(`_observations_repository.py:100`), which `no-silent-under-declaration` makes the
governing boundary for persisted observations. Merging or renaming either toward
the other would place an official and a non-official intake behind one verb.
