---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:222653e1a08e3f8b4cd206de331950f607a87f8257d455b134d5bd8d800a5a56'
step_id: 'S22'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Declare which of archive import file and artifact is the primary local input

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Changes

- `verify:` `archive import declares --file primary, --artifact auxiliary` -> `pass`

## Notes

No code change was required: the declaration landed correctly during the W01
locus sweep. `--file` is the required capsule and is primary; `--artifact` is
optional and its presence selects the machine-secret variant, so it configures
the operation rather than being its subject.
