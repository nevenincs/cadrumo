---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:076f7ebbfced7c13469eb20c78b55ea9ef2b52b9e7fc5dde2858c4cfc138a566'
step_id: 'S29'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Prove the spelling gate bites by mis-spelling a declared local-in file parameter

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `verify:` `scratchpad proof: eight mis-spellings, stale exemption, empty graph` -> `pass`

## Notes

The proof substitutes the gate's parameter accessor from a scratchpad script; no
tracked file under `src/` is mutated.
